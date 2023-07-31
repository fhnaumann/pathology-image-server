package ca.uhn.fhir.jpa.starter.interceptors;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.context.support.DefaultProfileValidationSupport;
import ca.uhn.fhir.jpa.starter.custom.ProprietaryFileReceiveHandler;
import ca.uhn.fhir.parser.DataFormatException;
import ca.uhn.fhir.parser.IParser;
import ca.uhn.fhir.rest.api.server.RequestDetails;

import ca.uhn.fhir.interceptor.api.Hook;
import ca.uhn.fhir.interceptor.api.Interceptor;
import ca.uhn.fhir.interceptor.api.Pointcut;
import ca.uhn.fhir.validation.FhirValidator;
import ca.uhn.fhir.validation.ValidationResult;
import org.hl7.fhir.common.hapi.validation.support.CachingValidationSupport;
import org.hl7.fhir.common.hapi.validation.support.PrePopulatedValidationSupport;
import org.hl7.fhir.common.hapi.validation.support.ValidationSupportChain;
import org.hl7.fhir.common.hapi.validation.validator.FhirInstanceValidator;
import org.hl7.fhir.r4.model.*;
import org.hl7.fhir.utilities.json.model.JsonArray;
import org.hl7.fhir.utilities.json.model.JsonObject;
import org.keycloak.TokenVerifier;
import org.keycloak.adapters.springsecurity.token.KeycloakAuthenticationToken;
import org.keycloak.authorization.client.AuthzClient;
import org.keycloak.authorization.client.resource.AuthorizationResource;
import org.keycloak.common.VerificationException;
import org.keycloak.representations.AccessToken;
import org.keycloak.representations.idm.authorization.AuthorizationResponse;
import org.opencds.cqf.cql.engine.exception.Severity;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.*;
import java.sql.SQLException;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.stream.Collectors;

@Interceptor
public class WSIUploadInterceptor
{

	private static final org.slf4j.Logger ourLog = org.slf4j.LoggerFactory.getLogger(WSIUploadInterceptor.class);

	//public static final String OWN_SERVER_URL = "http://localhost:8080/fhir/"; // change-me
	public static final String OWN_SERVER_URL = "http://hapi-fhir-dev:8080/fhir/"; // change-me

	private static final CachingValidationSupport cache = setupValidation();

	private static CachingValidationSupport setupValidation() {
		FhirContext ctx = FhirContext.forR4();
		ValidationSupportChain supportChain = new ValidationSupportChain();
		DefaultProfileValidationSupport defaultSupport = new DefaultProfileValidationSupport(ctx);
		supportChain.addValidationSupport(defaultSupport);
		PrePopulatedValidationSupport prePopulatedSupport = new PrePopulatedValidationSupport(ctx);
		IParser parser = ctx.newJsonParser();
		InputStream is = WSIUploadInterceptor.class.getResourceAsStream("/DicomTag.StructureDefinition.json");
		StructureDefinition structureDefinition = parser.parseResource(StructureDefinition.class, is);
		prePopulatedSupport.addStructureDefinition(structureDefinition);
		supportChain.addValidationSupport(prePopulatedSupport);
		return new CachingValidationSupport(supportChain);
	}

	private void writeKeycloakAccessTokenToRequestDetails(RequestDetails toWriteTo, HttpServletRequest theRequest) {
		KeycloakAuthenticationToken token = (KeycloakAuthenticationToken) theRequest.getUserPrincipal();
		if(token != null) {
			AccessToken accessToken = token.getAccount().getKeycloakSecurityContext().getToken();
			toWriteTo.setAttribute("access_token", accessToken);
			ourLog.info("Wrote access token to request details.");
		}
		else {
			// code below here only exists to allow for navigation in the Tester UI
			String stringToken = theRequest.getHeader("Authorization");
			if(stringToken == null) {
				ourLog.warn("User has no bearer token.");
				return;
			}
			try {
				AccessToken accessToken = TokenVerifier.create(stringToken.replace("Bearer ", ""), AccessToken.class).getToken();
				toWriteTo.setAttribute("access_token", accessToken);
			} catch (VerificationException e) {
				throw new RuntimeException(e);
			}
		}

	}

	CompletableFuture<Void> reference;
    @Hook(Pointcut.SERVER_INCOMING_REQUEST_POST_PROCESSED)
    public boolean postDocumentReference(RequestDetails theRequestDetails, HttpServletRequest theRequest, HttpServletResponse theResponse) throws IOException {
		 writeKeycloakAccessTokenToRequestDetails(theRequestDetails, theRequest);
		 if(theRequest.getMethod().equals("POST") && theRequestDetails.getResourceName().equals("DocumentReference")) {
			 ourLog.info("Custom Interceptor triggered by POST request from {}!", theRequest.getRemoteAddr());
			 if(!hasCreateFHIRDocumentReferenceResourceRole(theRequestDetails)) {
				 ourLog.info("User has no bearer token. Reject access.");
				 JsonObject responseToClient = new JsonObject();
				 theResponse.setStatus(HttpServletResponse.SC_FORBIDDEN);
				 PrintWriter writer = theResponse.getWriter();
				 writer.write(responseToClient.toString());
				 return false;
			 }
			 try {
				 final String json = getBody(theRequest);
				 ourLog.debug("Converted request body to string {}", json);
				 String responseToClient = "";

				 // pre-validation (disabled for now)
				 // Disabled because it always fails:
				 // - It does not find custom extensions (fixable)
				 // - It fails to acknowledge DocumentReference.status="current" as a valid code,
				 //   despite it being valid (https://hl7.org/fhir/r4b/valueset-document-reference-status.html).
				 // - It fails to acknowledge DocumentReference.content[0].attachment.contentType="application"/gzip"
				 //   as a valid code, despite it being valid (https://wiki.selfhtml.org/wiki/MIME-Type/%C3%9Cbersicht).
				 //   As an alternative "application/x-tar" may be used instead.

				 FhirContext ctx = FhirContext.forR4();
				 //FhirInstanceValidator validatorModule = new FhirInstanceValidator(cache);
				 //FhirValidator validator = ctx.newValidator().registerValidatorModule(validatorModule);
				 //ValidationResult result = validator.validateWithResult(json);

				 //if(!result.isSuccessful()) {
				 if(false) {
//					 JsonArray errors = new JsonArray();
//					 result.getMessages().forEach(singleValidationMessage -> {
//					 errors.add(singleValidationMessage.toString());
//					 });
//					 responseToClient.add("errors", errors);
//					 theResponse.setStatus(422); // 422 (Unprocessable Entity)
					 ourLog.warn("Pre-validation failed because the incoming request is not formatted appropriately to the custom StructureDefinition.");
				 }
				 else {
					 // generate businessID and return it to the client without handling the files
					 UUID businessID = ProprietaryFileReceiveHandler.generateUUID();
					 ourLog.info("Generated business ID={}", businessID);

					 try {
						 ProprietaryFileReceiveHandler.insertToDatabase(
							 businessID,
							 "",
							 ProprietaryFileReceiveHandler.PROP_DB_CONTAINER_NAME,
							 ProprietaryFileReceiveHandler.PROP_DB_NAME,
							 ProprietaryFileReceiveHandler.PROP_DB_USERNAME,
							 ProprietaryFileReceiveHandler.PROP_DB_PASSWORD);
					 } catch (SQLException e) {
						 throw new RuntimeException(e);
					 }

					 //ProprietaryFileReceiveHandler.createAndSendTaskResourceForStatus(businessID);
					 OperationOutcome operationOutcome = new OperationOutcome();
					 OperationOutcome.OperationOutcomeIssueComponent issue = new OperationOutcome.OperationOutcomeIssueComponent();
					 issue.setSeverity(OperationOutcome.IssueSeverity.INFORMATION);
					 issue.setCode(OperationOutcome.IssueType.INCOMPLETE); // "INFORMATIONAL" or "SUCCESS" may also be applicable
					 CodeableConcept uuidInfo = new CodeableConcept();
					 Coding coding = new Coding();
					 coding.setSystem("urn:uuid");
					 coding.setCode(String.format("urn:uuid:%s", businessID.toString()));
					 uuidInfo.addCoding(coding);
					 issue.setDetails(uuidInfo);
					 operationOutcome.addIssue(issue);
					 IParser parser = ctx.newJsonParser();
					 responseToClient = parser.encodeResourceToString(operationOutcome);
					 theResponse.setStatus(HttpServletResponse.SC_ACCEPTED);
					 AccessToken token = (AccessToken) theRequestDetails.getAttribute("access_token");
					 String keycloakRequesterId = token.getSubject();
					 ourLog.info("Request incoming from user with id: {}", keycloakRequesterId);
					 ProprietaryFileReceiveHandler.handle(json, businessID, keycloakRequesterId);
					 ourLog.info("Returned business ID to client.");
				 }
				 PrintWriter writer = theResponse.getWriter();
				 writer.write(responseToClient);
				 writer.flush();
			 } catch (IOException e) {
				 throw new RuntimeException(e);
			 } catch (DataFormatException e) {
				 ourLog.info("Not a document reference resource!");
				 theRequest.getReader().reset();
				 return true;
			 }

			 // stop HAPI from processing the request because we will manually provide a response once
			 // the file is correctly converted (may take some time though)
			 return false;
		 }
		 return true;
    }

	 private boolean hasCreateFHIRDocumentReferenceResourceRole(RequestDetails requestDetails) {
		 AccessToken accessToken = (AccessToken) requestDetails.getAttribute("access_token");
		 AccessToken.Access realmAccess = accessToken.getRealmAccess();
		 return realmAccess.getRoles().contains(KeycloakAuthorizationInterceptor.ROLE_CREATE);
	 }

	 private String getBody(HttpServletRequest request) throws IOException {
		return request.getReader().lines().collect(Collectors.joining());
	 }
}
