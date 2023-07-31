package ca.uhn.fhir.jpa.starter.interceptors;

import ca.uhn.fhir.jpa.searchparam.matcher.AuthorizationSearchParamMatcher;
import ca.uhn.fhir.jpa.searchparam.matcher.SearchParamMatcher;
import ca.uhn.fhir.jpa.starter.custom.ProprietaryFileReceiveHandler;
import ca.uhn.fhir.rest.api.RestOperationTypeEnum;
import ca.uhn.fhir.rest.api.server.RequestDetails;
import ca.uhn.fhir.rest.server.interceptor.auth.AuthorizationInterceptor;
import ca.uhn.fhir.rest.server.interceptor.auth.FhirQueryRuleTester;
import ca.uhn.fhir.rest.server.interceptor.auth.IAuthRule;
import ca.uhn.fhir.rest.server.interceptor.auth.RuleBuilder;
import ca.uhn.fhir.rest.server.interceptor.consent.RuleFilteringConsentService;
import org.hl7.fhir.r4.model.IdType;
import org.hl7.fhir.r4.model.ImagingStudy;
import org.hl7.fhir.r4.model.Patient;
import org.keycloak.representations.AccessToken;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationContext;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class KeycloakAuthorizationInterceptor extends AuthorizationInterceptor {

	private static final org.slf4j.Logger ourLog = org.slf4j.LoggerFactory.getLogger(KeycloakAuthorizationInterceptor.class);
	public static final String ROLE_CREATE = "create_resource"; // change-me
	public static final String ROLE_ADMIN = "admin"; // change-me
	private static final String ROLE_CONVERTER_FHIR_UPLOAD = "converter_fhir_upload"; // change-me

	private final SearchParamMatcher searchParamMatcher;

	public KeycloakAuthorizationInterceptor(ApplicationContext appContext) {
		super();
		searchParamMatcher = appContext.getBean(SearchParamMatcher.class);
	}

	private boolean userHasConverterFHIRUploadRole(AccessToken.Access realmAccess) {
		return realmAccess.getRoles().contains(ROLE_CONVERTER_FHIR_UPLOAD);
	}

	private boolean isAdmin(AccessToken.Access realmAccess) {
		return realmAccess.getRoles().contains(ROLE_ADMIN);
	}

	@Override
	public List<IAuthRule> buildRuleList(RequestDetails theRequestDetails) {
		ourLog.debug("Triggered auth interceptor.");
		AccessToken accessToken = (AccessToken) theRequestDetails.getAttribute("access_token");
		if(accessToken == null) {
			// something terrible has happened since the FHIR server should be protected by Keycloak. Any unauthenticated
			// access should have been stopped and redirected to Keycloak.
			throw new RuntimeException("Access token is null, which should never happen because this server is protected by Keycloak.");
		}
		AccessToken.Access realmAccess = accessToken.getRealmAccess();
		if(realmAccess == null) {
			return new RuleBuilder().denyAll().build();
		}
		if(isAdmin(realmAccess)) {
			ourLog.info("Admin detected. Grant access.");
			return new RuleBuilder().allowAll().build();
		}

		if(userHasConverterFHIRUploadRole(realmAccess)) {
			ourLog.info("FHIR converter uploader detected. Grant access.");
			return new RuleBuilder()
				.allow()
				.read()
				.resourcesOfType("Patient")
				.withAnyId()
				.andThen()
				.allow()
				.create()
				.resourcesOfType("Patient")
				.withAnyId()
				.andThen()
				.allow()
				.create()
				.resourcesOfType("ImagingStudy")
				.withAnyId()
				.build();
		}
		setAuthorizationSearchParamMatcher(new AuthorizationSearchParamMatcher(searchParamMatcher));
		RuleBuilder ruleBuilder = new RuleBuilder();
		boolean atLeastOneRole = false;
		for(String role : realmAccess.getRoles()) {
			if(role.startsWith("patient_")) {
				atLeastOneRole = true;
				String patientID = role.replace("patient_", "").strip();
				ourLog.debug("Allowing patient resource with id={}", patientID);
				ruleBuilder
					.allow()
					.read()
					.resourcesOfType(Patient.class)
					.withAnyId()
					//.operation().named("everything").onInstancesOfType(Patient.class).andAllowAllResponses().withFilterTester(String.format("identifier=urn:uuid:%s", patientID))
					//.withFilter(String.format("identifier=urn:uuid:%s", patientID));
					.withFilterTester(String.format("identifier=urn:uuid:%s", patientID));
			}
			else if(role.startsWith("imaging_study_")) {
				atLeastOneRole = true;
				String imagingStudyID = role.replace("imaging_study_", "").strip();
				ourLog.debug("Allowing imaging study resource with id={}", imagingStudyID);
				ruleBuilder
					.allow()
					.read()
					.resourcesOfType(ImagingStudy.class)
					.withAnyId()
					.withFilterTester(String.format("identifier=urn:uuid:%s", imagingStudyID));
			}
		}
		if(atLeastOneRole) {
			return ruleBuilder.build();
		}
		ourLog.warn("Not enough privileges. Reject access.");
		return ruleBuilder.denyAll().build();
	}
}
