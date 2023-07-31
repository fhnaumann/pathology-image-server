import requests
from requests.auth import HTTPBasicAuth
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.imagingstudy import ImagingStudy, ImagingStudySeries, ImagingStudySeriesInstance
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.endpoint import Endpoint
import sender
import pydicom

import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s", datefmt="%d/%b/%Y %H:%M:%S")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CONTAINER_NAME = "hapi-fhir-dev" # change-me
PORT = 8080 # change-me
HAPI_WEB_URL = f"http://{CONTAINER_NAME}:{PORT}/fhir" # change-me

HAPI_USERNAME = "admin" # secret-me
HAPI_PASSWORD = "admin" # secret-me

def construct_fhir_imaging_study(business_id: str, fhir_patient_reference_path: str, ds_list: list[pydicom.Dataset]) -> ImagingStudy:
    """
    Construct a FHIR ImagingStudy based on the DICOM dataset.

    :param business_id: The ID assigned to to this unique conversion, which was also returned to the uploading client.
    :type business_id: str
    :param fhir_patient_reference_path: A valid FHIR reference path (something like "Patient/3").
    :type fhir_patient_reference_path: str
    :param ds_list: The DICOM datasets which were uploaded to the PACS.
    :type ds_list: list[pydicom.Dataset]
    :return: A ImagingStudy which can be uploaded on a FHIR server.
    :rtype: ImagingStudy
    """
    study = ImagingStudy(
        status="available",
        subject=_construct_patient_reference(fhir_patient_reference_path)
    )
    study.identifier = []
    study.identifier.append(_get_business_id_as_fhir_identifier(business_id))
    study.identifier.append(_get_study_uid_as_fhir_identifier(ds_list[0].StudyInstanceUID))
    study.modality = [_get_modality_as_fhir_coding(ds_list[0].Modality)] # use "SM" instead of "112703"


    study.contained = [sender.get_wado_rs_endpoint_to_("study", business_id), 
                       sender.get_wado_rs_endpoint_to_("series", business_id)
                       ]

    study.endpoint = []
    dicom_web_study_endpoint = Reference()
    dicom_web_study_endpoint.reference = "#study"
    study.endpoint.append(dicom_web_study_endpoint)
    study.numberOfSeries = 1
    study.numberOfInstances = len(ds_list)
    study.series = [_construct_imaging_study_series(ds_list)]
    logging.debug("Constructed FHIR ImagingStudy.")
    return study

def _construct_imaging_study_series(ds_list: list[pydicom.Dataset]) -> ImagingStudySeries:
    """
    Construct a FHIR ImagingStudySeries.

    :param ds_list: The DICOM datasets which were uploaded to the PACS.
    :type ds_list: list[pydicom.Dataset]
    :return: A FHIR ImagingStudySeries
    :rtype: ImagingStudySeries
    """
    series = ImagingStudySeries(
        uid=ds_list[0].SeriesInstanceUID,
        modality=_get_modality_as_fhir_coding(ds_list[0].Modality) # use "SM" instead of "112703"
    )
    series.number = "1" # a study contains exactly one series with the id always being "1"
    series.endpoint = []
    dicom_web_series_endpoint = Reference()
    dicom_web_series_endpoint.reference = "#series"
    series.endpoint.append(dicom_web_series_endpoint)
    series.instance = _construct_imaging_study_instances(ds_list)
    logger.debug("Constructed FHIR ImagingStudySeries.")
    return series

def _construct_imaging_study_instances(ds_list: list[pydicom.Dataset]) -> list[ImagingStudySeriesInstance]:
    """
    Construct FHIR ImagingStudySeriesInstances as a list.

    :param ds_list: The DICOM datasets which were uploaded to the PACS.
    :type ds_list: list[pydicom.Dataset]
    :return: A list of FHIR ImagingStudySeriesInstances
    :rtype: list[ImagingStudySeriesInstance]
    """
    instances = []
    for sop_instance in ds_list:
        instance = ImagingStudySeriesInstance(
            uid=sop_instance.SOPInstanceUID,
            sopClass=_get_instance_sop_class_as_fhir_coding(sop_instance.SOPClassUID),
            number=sop_instance.InstanceNumber
        )
        instances.append(instance)
        logger.debug("Constructed FHIR ImagingStudySeriesInstance number %s.", sop_instance.InstanceNumber)
    logger.debug("Constructed FHIR ImagingStudySeriesInstances")
    return instances

def _construct_patient_reference(fhir_patient_reference_path: str) -> Reference:
    """
    Construct a FHIR Reference based on the reference string.

    :param fhir_patient_reference_path: A valid FHIR reference path (something like "Patient/3").
    :type fhir_patient_reference_path: str
    :return: A FHIR reference to the patient reference string.
    :rtype: Reference
    """
    patient_reference = Reference()
    patient_reference.reference = fhir_patient_reference_path
    patient_reference.type = "Patient"
    logger.debug("Constructed FHIR Patient Reference.")
    return patient_reference
    
def _get_instance_sop_class_as_fhir_coding(sop_class_uid: str) -> Coding:
    """
    Construct a FHIR Coding with the SOPClassUID from the DICOM files.


    :param sop_class_uid: The SOPClassUID in a DICOM file.
    :type sop_class_uid: str
    :return: A FHIR Coding containing the SOPClassUID.
    :rtype: Coding
    """
    c = Coding()
    # https://hl7.org/fhir/r4b/identifier-registry.html
    # "urn:dicom:uid" may also be applicable as the SOPClassUID follows DICOM OID rules.
    c.system = "urn:dicom:uid"
    c.code = f"urn:oid:{sop_class_uid}"
    return c

def _get_modality_as_fhir_coding(modality: str) -> Coding:
    """
    Construct a FHIR Coding with the Modality from the DICOM files.

    :param modality: The Modality in a DICOM file.
    :type modality: str
    :return: A FHIR Coding containing the Modality.
    :rtype: Coding
    """
    #c = CodeableConcept()
    #c.coding = []
    coding = Coding()
    # The DICOM modality will most likely be "SM" (Slide Microscopy), 
    # which is the closest to WSI available for that DICOM field (see
    # https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.3.html#sect_C.7.3.1.1.1)
    #
    # The FHIR Binding has an extensible binding to https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_CID_29.html
    # which only includes "SM" but not "112703"
    # In FHIR the system can also the a broader field with http://dicom.nema.org/resources/ontology/DCM.
    # In this definition "112703" (Wholde Slide Imaging) is also included. So "112703" may also be used.
    coding.system = "http://dicom.nema.org/resources/ontology/DCM"
    coding.code = modality
    #c.coding.append(coding)
    #return c
    return coding

def _get_business_id_as_fhir_identifier(business_id: str) -> Identifier:
    """
    Construct a FHIR Identifier with the business ID

    :param business_id: The ID assigned to to this unique conversion, which was also returned to the uploading client.
    :type business_id: str
    :return: A FHIR Identifier containing the business ID.
    :rtype: Identifier
    """
    idf = Identifier()
    # use "urn:uuid" since it's a UUID (see https://hl7.org/fhir/r4b/identifier-registry.html)
    idf.system = "urn:uuid"
    idf.value = f"urn:uuid:{business_id}"
    return idf

def _get_study_uid_as_fhir_identifier(study_uid: str) -> Identifier:
    """
    Construct a FHIR Identifier with the DICOM StudyInstanceUID.
    The StudyInstanceUID is just the business ID translated into a number.

    :param study_uid: The StudyInstanceUID in the DICOM file, obtained by converting the business ID into a number.
    :type study_uid: str
    :return: A FHIR identifier containing the StudyInstanceUID.
    :rtype: Identifier
    """
    idf = Identifier()
    # use "urn:dicom:uid" since it's a DICOM OID (see https://hl7.org/fhir/r4b/identifier-registry.html)
    idf.system = "urn:dicom:uid"
    idf.value = f"urn:oid:{study_uid}"
    return idf

def upload_imaging_study(fhir_imaging_study: ImagingStudy, header_with_auth: dict[str, str]) -> None:
    """
    Upload a FHIR ImagingStudy to a FHIR server.

    :param fhir_imaging_study: The FHIR ImagingStudy to be uploaded. It is a FHIR representation of the DICOM study uploaded to the PACS previously.
    :type fhir_imaging_study: ImagingStudy
    :param header_with_auth: HTTP header containing bearer token.
    :type header_with_auth: dict[str, str]
    :raises e: When a HTTP error occurred.
    """
    url = HAPI_WEB_URL + f"/ImagingStudy"
    headers = {
        "Accept":"application/fhir+json",
        "Content-Type":"application/fhir+json"
    } | header_with_auth
    to_upload = fhir_imaging_study.json()
    logger.debug("Uploading ImagingStudy with content %s", to_upload)
    r = requests.post(url, headers=headers, data=to_upload)
    try:
        r.raise_for_status()
    except Exception as e:
        logging.error("Error occurred while uploading ImagingStudy to FHIR server (url=%s, header=%s, status=%s). Error message '%s'", url, headers, r.status_code, e)
        raise e
    logger.info("Uploaded ImagingStudy to FHIR server.")


def patient_already_exists(patient_id: str, header_with_auth: dict[str, str]) -> str:
    """
    Checks the FHIR server if a patient is already associated with the given patient ID.

    :param patient_id: The business ID of the patient, not the resource ID (logical identifier)
    :type patient_id: str
    :param header_with_auth: HTTP header containing bearer token.
    :type header_with_auth: dict[str, str]
    :return: The string reference to the Patient (e.g. "Patient/3"). This includes the logical identifier.
    Returns an empty string if patient is not found on the FHIR server.
    :rtype: str
    """
    url = HAPI_WEB_URL + f"/Patient?identifier={patient_id}"
    r = requests.get(url, headers=header_with_auth)
    try:
        r.raise_for_status()
    except Exception as e:
        logging.error("Error occurred while accessing Patients on FHIR server (url=%s, header=%s, status=%s). Error message '%s'", url, header_with_auth, r.status_code, e)
        raise e
    info = r.json()
    try:
        entries: list = info["entry"]
        if(len(entries) == 0):
            logger.info("No existing patient with business ID '%s' found on the FHIR server.", patient_id)
            return ""
    except KeyError:
        logger.info("No existing patient with business ID '%s' found on the FHIR server.", patient_id)
        return ""
    resource = info["entry"][0]["resource"]
    reference_string = f"{resource['resourceType']}/{resource['id']}"
    logger.info("Found patient '%s' matching the business ID '%s' on the FHIR server.", reference_string, patient_id)
    return reference_string

def construct_fhir_patient(ds: pydicom.Dataset) -> Patient:
    """
    Construct a FHIR Patient with metadat from a DICOM dataset.
    Currently the following mappings are done:
    DICOM <-> FHR
    --------------
    PatientID <-> Patient.identifier
    PatientName <-> Patient.HumanName.given
    PatientSex <-> Patient.gender
    PatientBirthDate <-> Patient.birthDate

    The age in the DICOM file is not used as there is no native field in FHIR for that.

    :param ds: A DICOM dataset to extract metadata from.
    :type ds: pydicom.Dataset
    :return: A FHIR Patient.
    :rtype: Patient
    """
    p = Patient()
    
    p.identifier = [_get_business_id_as_fhir_identifier(business_id=ds.PatientID)]
    p.name = []
    hn = HumanName()
    hn.given = [str(ds.PatientName)]
    p.name.append(hn)
    p.gender = _dcm_2_fhir_gender(ds.PatientSex)
    p.birthDate = _dcm_2_fhir_date(ds.PatientBirthDate)
    p.active = True
    logging.debug("Constructed FHIR Patient.")
    return p

def _dcm_2_fhir_date(dicom_date: str) -> str:
    """
    Convert a DICOM "Date" (DA) to a FHIR "date".
    DICOM "Date" format: https://dicom.nema.org/dicom/2013/output/chtml/part05/sect_6.2.html
    FHIR "date" format: https://hl7.org/fhir/r4b/datatypes.html#date

    :param dicom_date: A date in the DICOM format.
    :type dicom_date: str
    :return: A date in the FHIR format.
    :rtype: str
    """
    year = dicom_date[:4]
    month = dicom_date[4:6]
    day = dicom_date[6:]
    print(f"{year}-{month}-{day}")
    return f"{year}-{month}-{day}"

def _dcm_2_fhir_gender(dicom_gender: str) -> str:
    """
    Convert a DICOM "PatientSex" to a FHIR "gender".
    DICOM "PatientSex" format: https://dicom.nema.org/dicom/2013/output/chtml/part03/sect_C.2.html#table_C.2-3
    FHIR "gender" format: https://hl7.org/fhir/r4b/valueset-administrative-gender.html

    :param dicom_gender: A gender in the DICOM format.
    :type dicom_gender: str
    :return: A gender in the FHIR format.
    :rtype: str
    """
    mapping = {
        "M": "male",
        "F": "female",
        "O": "other"
    }
    try:
        return mapping[dicom_gender]
    except KeyError:
        return "unknown"

def upload_patient(fhir_patient: Patient, header_with_auth: dict[str, str]) -> str:
    """
    Upload a FHIR Patient to a FHIR server.

    :param fhir_patient: The FHIR Patient to be uploaded.
    :type fhir_patient: Patient
    :param header_with_auth: HTTP header containing bearer token.
    :type header_with_auth: dict[str, str]
    :return: The reference string which can be used to create a reference to this patient (e.g. "Patient/3" where "3" is the logical identifier).
    :rtype: str
    """
    url = HAPI_WEB_URL + f"/Patient"
    headers = {
        "Accept":"application/fhir+json",
        "Content-Type":"application/fhir+json"
    } | header_with_auth
    to_upload = fhir_patient.json()
    logger.debug("Uploading Patient with content %s", to_upload)
    r = requests.post(url, headers=headers, data=to_upload)
    try:
        r.raise_for_status()
    except Exception as e:
        logger.error("Error occurred while uploading Patient to FHIR server (url=%s, header=%s, status=%s). Error message '%s'", url, headers, r.status_code, e)
        raise e
    info = r.json()
    reference_string = f"{info['resourceType']}/{info['id']}"
    logger.info("Uploaded Patient to FHIR server. Reference to Patient is %s", reference_string)
    return reference_string
