package ca.uhn.fhir.jpa.starter.custom;

import ca.uhn.fhir.model.api.annotation.ResourceDef;
import org.hl7.fhir.DocumentReference;

@ResourceDef(name = "DocumentReference", profile = "http://hapi-fhir-dev:8081/StructureDefinition/mydocumentreference")
public class MyDocumentReference extends DocumentReference {

	private static final long serialVersionUID = 1L;

}
