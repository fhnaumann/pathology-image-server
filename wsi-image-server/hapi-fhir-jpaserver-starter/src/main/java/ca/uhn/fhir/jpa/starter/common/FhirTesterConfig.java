package ca.uhn.fhir.jpa.starter.common;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.jpa.starter.AppProperties;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.interceptor.BearerTokenAuthInterceptor;
import ca.uhn.fhir.rest.server.util.ITestingUiClientFactory;
import ca.uhn.fhir.to.FhirTesterMvcConfig;
import ca.uhn.fhir.to.TesterConfig;
import ca.uhn.fhir.to.client.BearerTokenClientFactory;
import org.apache.http.client.HttpClient;
import org.keycloak.authorization.client.AuthzClient;
import org.keycloak.representations.AccessTokenResponse;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;

import javax.servlet.http.HttpServletRequest;
import java.util.Map;

//@formatter:off
/**
 * This spring config file configures the web testing module. It serves two
 * purposes:
 * 1. It imports FhirTesterMvcConfig, which is the spring config for the
 *    tester itself
 * 2. It tells the tester which server(s) to talk to, via the testerConfig()
 *    method below
 */
@Configuration
@Import(FhirTesterMvcConfig.class)
public class FhirTesterConfig {

	/**
	 * This bean tells the testing webpage which servers it should configure itself
	 * to communicate with. In this example we configure it to talk to the local
	 * server, as well as one public server. If you are creating a project to
	 * deploy somewhere else, you might choose to only put your own server's
	 * address here.
	 *
	 * Note the use of the ${serverBase} variable below. This will be replaced with
	 * the base URL as reported by the server itself. Often for a simple Tomcat
	 * (or other container) installation, this will end up being something
	 * like "http://localhost:8080/hapi-fhir-jpaserver-starter". If you are
	 * deploying your server to a place with a fully qualified domain name,
	 * you might want to use that instead of using the variable.
	 */
  @Bean
  public TesterConfig testerConfig(AppProperties appProperties) {
    TesterConfig retVal = new TesterConfig();
	  System.out.println("NEW TESTER CONFIG");
	 /*
	 Should never be deployed in production with these settings.
	 The code below allows the built-in client of hapi to skip any authentication.
	 This is done so the Tester-UI can be used. With this turned on, anyone who has access to the internal server URL
	 can do *everything* on the FHIR server.
	  */
	 retVal.setClientFactory((theFhirContext, theRequest, theServerBaseUrl) -> {
		 // create client
		 IGenericClient client = theFhirContext.newRestfulGenericClient(theServerBaseUrl);
		 // obtain keycloak user details
		 AuthzClient authzClient = AuthzClient.create(new org.keycloak.authorization.client.Configuration(
			 "http://keycloak:8080", // change-me
			 "myrealm", // change-me
			 "myclient", // change-me
			 Map.of("secret", "myclient-secret"), // secret-me
			 null
		 ));
		 AccessTokenResponse accessTokenResponse = authzClient.obtainAccessToken("fhir_admin", "fhir_admin"); // change-me
		 BearerTokenAuthInterceptor bearerTokenAuthInterceptor = new BearerTokenAuthInterceptor(accessTokenResponse.getToken());
		 client.registerInterceptor(bearerTokenAuthInterceptor);
		 return client;
	 });
    appProperties.getTester().forEach((key, value) -> {
		 retVal
			 .addServer()
			 .withId(key)
			 .withFhirVersion(value.getFhir_version())
			 .withBaseUrl(value.getServer_address())
			 .withName(value.getName())
			 .allowsApiKey();
		 retVal.setRefuseToFetchThirdPartyUrls(
			 value.getRefuse_to_fetch_third_party_urls());

	 });
    return retVal;
  }

}
//@formatter:on
