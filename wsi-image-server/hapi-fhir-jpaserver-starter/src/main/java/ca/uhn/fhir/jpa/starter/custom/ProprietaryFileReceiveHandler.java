package ca.uhn.fhir.jpa.starter.custom;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.jpa.starter.interceptors.WSIUploadInterceptor;
import ca.uhn.fhir.parser.DataFormatException;
import ca.uhn.fhir.parser.IParser;
import ca.uhn.fhir.rest.api.MethodOutcome;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.gclient.ICreateTyped;
import com.rabbitmq.client.*;

import org.hl7.fhir.r4.model.*;
import org.hl7.fhir.utilities.json.model.JsonArray;
import org.hl7.fhir.utilities.json.model.JsonObject;
import org.keycloak.adapters.springsecurity.client.KeycloakClientRequestFactory;
import org.keycloak.authorization.client.AuthzClient;
import org.keycloak.representations.idm.authorization.AuthorizationResponse;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeoutException;
import java.util.stream.Collectors;

public class ProprietaryFileReceiveHandler {

	private static final org.slf4j.Logger ourLog = org.slf4j.LoggerFactory.getLogger(ProprietaryFileReceiveHandler.class);

	public static final String PROP_DB_CONTAINER_NAME = "prop-postgres:5432"; // container name change-me
	public static final String PROP_DB_NAME = "prop"; // defined in db.sql in prop folder change-me
	public static final String PROP_DB_USERNAME = "postgres"; // defined in environment variables for prop-postgres container secret-me
	public static final String PROP_DB_PASSWORD = "postgres"; // defined in environment variables for prop-postgres container secret-me

	public static UUID generateUUID() {
		return UUID.randomUUID();
	}

	public static void handle(String json, UUID uuid, String keycloakUserID) {
		ourLog.info("Starting ProprietaryFileReceiveHandler on separate thread.");
		//CompletableFuture.runAsync(() -> {
			ourLog.info("Running ProprietaryFileReceiveHandler#handle async.");

			Exception exception = null;
			try {
				FhirContext context = FhirContext.forR4();
				IParser parser = context.newJsonParser();
				DocumentReference documentReference = parser.parseResource(DocumentReference.class, json);
				ourLog.debug("Parsed incoming request to DocumentReference.");
				byte[] decodedFile = documentReference.getContent().get(0).getAttachment().getData();
				if(decodedFile.length == 0) {
					ourLog.warn("DocumentReference contains no base64 encoded data.");
					throw new DataFormatException();
				}
				String pathToWsiTarball = writeToFile(uuid, decodedFile);
				insertToDatabase(uuid, pathToWsiTarball, PROP_DB_CONTAINER_NAME, PROP_DB_NAME, PROP_DB_USERNAME, PROP_DB_PASSWORD);
				String jsonUUIDAndFilepathAndDicomTags = compose(
					uuid,
					keycloakUserID,
					pathToWsiTarball,
					documentReference.getExtensionsByUrl("https://localhost:8080/fhir/StructureDefinition/DicomTag"),
					documentReference.getExtensionsByUrl("https://localhost:8080/fhir/StructureDefinition/PathInTarball")
				);
				sendToBroker(uuid, jsonUUIDAndFilepathAndDicomTags);
			} catch (DataFormatException e) {
				ourLog.info("POST request is not a DocumentReference or contains invalid format (maybe not base64 encoded data?).", e);
				exception = e;
			} catch (IOException e) {
				ourLog.info("Error writing the contents of the 'data' field to file!", e);
				exception = e;
			} catch (SQLException e) {
				ourLog.info("Error connecting to internal proprietary database!", e);
				exception = e;
			} catch (TimeoutException e) {
				ourLog.info("Error connecting to internal message broker", e);
				exception = e;
			} catch (Exception e) {
				ourLog.info("Generic exception occurred", e);
				exception = e;
			}
			finally {
				String errorMessage = "";
				if(exception != null) {
					StringWriter sw = new StringWriter();
					PrintWriter pw = new PrintWriter(sw);
					exception.printStackTrace(pw);
					errorMessage = sw.toString();
				}
				try {
					updatePropDBStatus(uuid, false, errorMessage, PROP_DB_CONTAINER_NAME, PROP_DB_NAME, PROP_DB_USERNAME, PROP_DB_PASSWORD);
				} catch (SQLException e) {
					//swallowing exception by throwing a new one in the 'finally' block is fine because it will be written to DB first,
					// which is desired (instead of printing it here)
					throw new RuntimeException(e);
				}
			}
		//});
	}



	public static void createAndSendTaskResourceForStatus(UUID uuid) {
		Task task = new Task();
		Identifier businessIdentifier = new Identifier();
		businessIdentifier.setSystem("urn:uuid");
		businessIdentifier.setValue(String.format("urn:uuid:%s", uuid.toString()));
		task.setIdentifier(List.of(businessIdentifier));
		task.setStatus(Task.TaskStatus.ACCEPTED);
		task.setIntent(Task.TaskIntent.UNKNOWN);
		CodeableConcept codeableConcept = new CodeableConcept();
		codeableConcept.setText(""); // potential errors will be written here
		task.setBusinessStatus(codeableConcept);
		FhirContext ctx = FhirContext.forR4();
		IGenericClient client = ctx.newRestfulGenericClient(WSIUploadInterceptor.OWN_SERVER_URL);
		ICreateTyped create = client.create().resource(task);
		String accessToken = getAdminAccessToken();
		System.out.println(client.getHttpClient());
		ourLog.info("setting header with " + accessToken);
		create.withAdditionalHeader(KeycloakClientRequestFactory.AUTHORIZATION_HEADER, accessToken);
		MethodOutcome outcome = create.execute();
		if(outcome.getCreated()) {
			ourLog.info("Successfully created task resource!");
		}
		else {
			ourLog.info("Error creating task resource! {}", outcome.getOperationOutcome());
		}

	}

	private static String getAdminAccessToken() {
		AuthzClient authzClient = AuthzClient.create();
		AuthorizationResponse response = authzClient.authorization("user", "user").authorize();
		return "Bearer " + response.getToken();
	}

	private static String writeToFile(UUID uuid, byte[] decodedFile) throws IOException {
		// ./app/create-data/* contains all proprietary files (see line 30 in Dockerfile for hapi-fhir)
		// in theory a different storage like S3 Buckets could be used too.
		final String pathInSharedVolume = String.format("./app/create-data/%s.tar.gz", uuid.toString());
		ourLog.info("Writing data to file as {}!", pathInSharedVolume);
		//Files.createDirectories(Paths.get("./app/create-data"));
		OutputStream stream = new FileOutputStream(pathInSharedVolume);
		stream.write(decodedFile);
		stream.close();
		ourLog.info("Successfully wrote data to file ({})", pathInSharedVolume);
		return pathInSharedVolume;
	}

	public static void insertToDatabase(UUID uuid, String pathToFile, String dbHost, String dbName, String user, String password) throws SQLException {
		final String url = String.format("jdbc:postgresql://%s/%s", dbHost, dbName);
		ourLog.info("Connecting to database {}", url);
		Connection connection = DriverManager.getConnection(url, user, password);
		String insert = "INSERT INTO data (id, path_to_file, converted) VALUES (?::UUID, ?, ?) ON CONFLICT (id) DO UPDATE " +
			"SET path_to_file = excluded.path_to_file, converted = excluded.converted;";
		boolean converted = false; // Cannot be converted at this point
		PreparedStatement preparedStatement = connection.prepareStatement(insert);
		preparedStatement.setString(1, uuid.toString());
		preparedStatement.setString(2, pathToFile);
		preparedStatement.setBoolean(3, converted);
		preparedStatement.executeUpdate();
		connection.close();
		ourLog.info("Successfully wrote id={}, path_to_file={}, converted={} to database!", uuid, pathToFile, converted);
	}

	private static String compose(UUID uuid, String keycloakUserID, String pathToWsiTarball, List<Extension> dicomExtensions, List<Extension> pathInTarballExtensions) {
		if(pathInTarballExtensions.size() != 1) {
			throw new DataFormatException(String.format("Exactly one (1) path should be supplied for key %s!", "https://localhost:8080/fhir/StructureDefinition/PathInTarball"));
		}
		// dicomExtensions is a list where each extension contains the two extensions (key and value)

		JsonObject composed = new JsonObject();
		composed.add("uuid", uuid.toString());
		composed.add("keycloak_user_id", keycloakUserID);
		composed.add("path_to_wsi_tarball", pathToWsiTarball);
		composed.add("path_in_tarball_for_openslide", pathInTarballExtensions.get(0).getValue().primitiveValue());
		if(dicomExtensions.isEmpty()) {
			composed.add("tags", new JsonArray()); // set empty tags array so key is at least present
			ourLog.info("No additional dicom tags supplied as extension to DocumentReference!");
			return composed.toString();
		}

		List<JsonObject> dicomTags = dicomExtensions.stream().map(dcmTagExtension -> keyValuePair(dcmTagExtension)).collect(Collectors.toList());
		JsonArray dicomTagArray = new JsonArray();
		dicomTags.forEach(dicomTag -> dicomTagArray.add(dicomTag));
			composed.add("tags", dicomTagArray);
		return composed.toString();
	}

	private static JsonObject keyValuePair(Extension extension) {
		Extension dicomKey = extension.getExtensionByUrl("dcm_key");
		Extension dicomValue = extension.getExtensionByUrl("dcm_value");
		String keyPrimitive = dicomKey.getValue().primitiveValue();
		String valuePrimitive = dicomValue.getValue().primitiveValue();
		ourLog.info("Found key value pair ({},{})!", keyPrimitive, valuePrimitive);
		return new JsonObject()
			.add("key", keyPrimitive)
			.add("value", valuePrimitive);
	}

	private static void sendToBroker(UUID uuid, String jsonToSend) throws IOException, TimeoutException {
		final String messageBrokeURL = "rabbitmq"; // container name change-me
		final int port = 5672; // default port change-me
		ourLog.info("Connecting to message broker {}:{}", messageBrokeURL, port);
		ConnectionFactory factory = new ConnectionFactory();
		factory.setHost(messageBrokeURL);
		factory.setPort(port);
		com.rabbitmq.client.Connection connection = factory.newConnection();
		Channel channel = connection.createChannel();

		final String queue = "hello"; // matches queue name in converter script change-me
		channel.queueDeclare(queue, false, false, false, null);
		channel.basicPublish("", queue, null, jsonToSend.getBytes(StandardCharsets.UTF_8));
		ourLog.info("Published {} to the broker on queue {}", jsonToSend, queue);

		channel.close();
	}

	private static void updatePropDBStatus(UUID businessID, boolean converted, String errorMessage, String dbHost, String dbName, String user, String password) throws SQLException {
		final String url = String.format("jdbc:postgresql://%s/%s", dbHost, dbName);
		ourLog.info("Connecting to database {}", url);
		Connection connection = DriverManager.getConnection(url, user, password);
		String update = "UPDATE data SET converted=?, error_msg=? WHERE id=?::UUID";
		PreparedStatement preparedStatement = connection.prepareStatement(update);
		preparedStatement.setString(3, businessID.toString());
		preparedStatement.setBoolean(1, converted);
		preparedStatement.setString(2, errorMessage);
		preparedStatement.executeUpdate();
		connection.close();
		ourLog.info("Updated the database with error message {}", errorMessage);
	}
}
