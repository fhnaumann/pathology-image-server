import requests
from requests.auth import HTTPBasicAuth
import os
import shutil
import uuid
from fhir.resources.R4B.imagingstudy import *
from fhir.resources.R4B import patient, endpoint, codeableconcept, coding
import conversion_util
import pydicom
from fhir_communication import fhir_handler
import psycopg2
import pprint
import exceptions
import typing
from keycloak import KeycloakOpenID, KeycloakAdmin, KeycloakOpenIDConnection
from keycloak_info import KeycloakInfo
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s", datefmt="%d/%b/%Y %H:%M:%S")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CONTAINER_NAME = "orthanc-pacs" # change-me
PORT = 8042 # change-me
DICOM_WEB_SERVER_NAME = "dicom-web" # change-me
DICOM_WEB_URL = f"http://{CONTAINER_NAME}:{PORT}/{DICOM_WEB_SERVER_NAME}" # change-me

ORTHANC_USERNAME = "orthanc" # specified in environment variables for orthanc-docker secret-me
ORTHANC_PASSWORD = "orthanc" # specified in environment variables for orthanc-docker secret-me
ORTHANC_URL = f"http://{CONTAINER_NAME}:{PORT}" # url name is the container name; port is defined in the docker-compose change-me

STUDY_UID_WITH_PREFIX = lambda business_id: f"2.25.{conversion_util.from_uuid_dcm_uid(business_id)}"

KEYCLOAK_URL = "http://keycloak:8080" # change-me
CLIENT_NAME = "myclient" # change-me
CLIENT_SECRET = "myclient-secret" # secret-me
REALM_NAME = "myrealm" # change-me

CONVERTER_FHIR_UPLOADER_NAME = "converter_fhir_uploader" # secret-me
CONVERTER_FHIR_UPLOADER_PASSWORD = "converter_fhir_uploader" # secret-me

CONVERTER_PACS_UPLOADER_NAME = "converter_pacs_uploader" # secret-me
CONVERTER_PACS_UPLOADER_PASSWORD = "converter_pacs_uploader" # secret-me

FHIR_ADMIN_NAME = "fhir_admin" # secret-me
FHIR_ADMIN_PASSWORD = "fhir_admin" # secret-me


def send_and_cleanup(business_id: str, kc_info: KeycloakInfo, path_to_dcm_folder: str):
    """
    Sends the dicom images to the PACS server (orthanc) through the Orthanc REST-API. 
    Then a ImagingStudy is constructed with a WADO-RS endpoint and sent to the FHIR server (HAPI) through the FHIR REST-API.
    Then the necessary roles are created and assigned to the user in Keycloak through the Keycloak REST-API.
    Lastly all the temporary DICOM files are deleted from the filepath.

    :param business_id: The business ID for the DICOM study and FHIR ImagingStudy.
    :type business_id: str
    :param kc_info: Object containing relevant information from the Keycloak user which initiated the upload.
    :type kc_info: KeycloakInfo
    :param path_to_dcm_folder: Path where the DICOM files are located on the system.
    :type path_to_dcm_folder: str
    :raises exceptions.UploadToPacsException: An error occurred while uploading to the PACS server.
    :raises exceptions.UploadToFHIRException: An error occurred while uploading to the FHIR server.
    :raises exceptions.GrantKeycloakRoleException: An error occurred while creating and/or assigning the roles to the user.
    """
    keycloak_openid = KeycloakOpenID(
        server_url=KEYCLOAK_URL,
        client_id=CLIENT_NAME,
        realm_name=REALM_NAME,
        client_secret_key=CLIENT_SECRET
    )

    fhir_token: dict = keycloak_openid.token(
        username=CONVERTER_FHIR_UPLOADER_NAME,
        password=CONVERTER_FHIR_UPLOADER_PASSWORD
    )
    fhir_access_token = fhir_token["access_token"]
    logger.debug("User %s got access token %s", CONVERTER_FHIR_UPLOADER_NAME, fhir_access_token)
    fhir_header_with_auth = {
        "Authorization": f"Bearer {fhir_access_token}"
    }

    pacs_token: dict = keycloak_openid.token(
        username=CONVERTER_PACS_UPLOADER_NAME,
        password=CONVERTER_PACS_UPLOADER_PASSWORD
    )
    pacs_access_token = pacs_token["access_token"]
    logger.debug("User %s got access token %s", CONVERTER_PACS_UPLOADER_NAME, pacs_access_token)
    pacs_header_with_auth = {
        "Authorization": f"Bearer {pacs_access_token}"
    }

    try:
        send_to_pacs(path_to_dcm_folder, pacs_header_with_auth)
        logger.debug("Sent to PACS.")
    except Exception as e:
        logger.exception("Exception occurred while uploading to PACS %s", e)
        raise exceptions.UploadToPacsException("Uploading to PACS failed!") from e
    pat_id = None
    try:
        pat_id = send_to_fhir(path_to_dcm_folder, business_id, fhir_header_with_auth)
        logger.debug("Sent to FHIR.")
    except Exception as e:
        logger.exception("Exception occurred while uploading to FHIR %s", e)
        raise exceptions.UploadToFHIRException("Uploading to FHIR failed!") from e
    if pat_id is not None: # skip this step if the resource failed to be sent to the FHIR server
        try:
            create_and_assign_keycloak_roles(business_id, pat_id, kc_info)
            logger.debug("Created and assigned Keycloak roles.")
        except Exception as e:
            logger.exception("Exception occurred while creating and/or assigning Keycloak roles %s", e)
            raise exceptions.GrantKeycloakRoleException("Creating or granting necessary roles failed!") from e
    cleanup(os.path.join("./temp_data", business_id))

def create_and_assign_keycloak_roles(imaging_study_id: str, patient_id: str, kc_info: KeycloakInfo):
    # use "special" admin user to create te
    keycloak_conn = KeycloakOpenIDConnection(
        server_url=KEYCLOAK_URL,
        username=FHIR_ADMIN_NAME,
        password=FHIR_ADMIN_PASSWORD,
        realm_name=REALM_NAME,
        # client_id=CLIENT_NAME,
        # client_secret_key=CLIENT_SECRET,
        verify=False)
    keycloak_admin = KeycloakAdmin(connection=keycloak_conn)
    logger.debug("Initiated connection as Keycloak admin.")

    imaging_study_role_name = f"imaging_study_{imaging_study_id}"
    patient__role_name = f"patient_{patient_id}"

    imaging_study_role_repr = {
        "name": imaging_study_role_name
    }
    patient_role_repr = {
        "name": patient__role_name
    }
    # do not wrap payload with json.dumps() into a string, create_realm_role will do that internally.
    keycloak_admin.create_realm_role(payload=imaging_study_role_repr, skip_exists=True) # TODO: skip_exists only for debugging
    logger.info("Created Keycloak role %s", imaging_study_role_name)
    keycloak_admin.create_realm_role(payload=patient_role_repr, skip_exists=True) # may already exist, if the patient resource also already existed
    logger.info("Created Keycloak role %s", patient__role_name)

    imaging_study_realm_role = keycloak_admin.get_realm_role(role_name=imaging_study_role_name)
    patient_realm_role = keycloak_admin.get_realm_role(role_name=patient__role_name)
    roles_to_assign = [imaging_study_realm_role, patient_realm_role]
    keycloak_admin.assign_realm_roles(user_id=kc_info.user_id, roles=roles_to_assign)
    logger.info("Assigned roles %s to user %s", roles_to_assign, kc_info.user_id)

def update_prop_db_status(business_id: str, converted: bool, error_msg: str=""):
    
    conn = psycopg2.connect(
        host="prop-postgres", # container name change-me
        port="5432", # port defined in docker-compose.yml change-me
        database="prop", # defined in db.sql in prop folder change-me
        user="postgres", # defined in environment variables for prop-postgres container secret-me
        password="postgres" # defined in environment variables for prop-postgres container secret-me
    )
    logger.debug("Established connection to prop database.")
    cur = conn.cursor()
    sql = \
        """
        UPDATE data
        SET converted=%s, error_msg=%s
        WHERE id=%s::UUID
        """
    cur.execute(sql, (converted, error_msg, business_id))
    conn.commit()
    logger.info("Updated prop database with converted=%s and error_msg=%s for user=%s", converted, error_msg, business_id)
    if error_msg == "":
        logger.info("No error occurred.")
    cur.close()
    conn.close()

def cleanup(path_to_delete: str):
    """
    Cleanup after "converter" container is done.

    :param path_to_delete: Path where all the files will be deleted.
    :type path_to_delete: str
    """
    logger.info("Deleting folder (and subfolders) %s", path_to_delete)
    shutil.rmtree(path_to_delete)

def send_to_pacs(path_to_dcm_folder: str, pacs_header_with_auth: dict[str, str]):
    """
    Send dicom files to PACS.

    :param path_to_dcm_folder: Path where the DICOM files are located on the system.
    :type path_to_dcm_folder: str
    :param pacs_header_with_auth: HTTP header containing bearer token.
    :type pacs_header_with_auth: dict[str, str]
    """
    logger.debug("Sending to PACS...")
    for dcm_file in os.scandir(path_to_dcm_folder):
            if os.path.isfile(dcm_file):
                upload_file(dcm_file, pacs_header_with_auth)

def upload_file(path, pacs_header_with_auth: dict[str, str]):
    with open(path, "rb") as f:
        dicom = f.read()
        # print("Uploading: %s (%dMB)" % (path, len(dicom) / (1024 * 1024)))
        upload_buffer(dicom, pacs_header_with_auth)

def upload_buffer(dicom, pacs_header_with_auth: dict[str, str]) -> None:
    url = "%s/instances" % ORTHANC_URL
    r = requests.post(url, headers=pacs_header_with_auth, data=dicom)
    try:
        r.raise_for_status()
    except Exception as e:
        logging.error("Error occurred while uploading DICOM file to PACS server (url=%s, header=%s, status=%s). Error message '%s'", url, pacs_header_with_auth, r.status_code, e)
        raise e
    logger.debug("Uploaded a single DICOM file.")

def get_wado_rs_endpoint_to_(type: typing.Literal["study", "series"], business_id: str) -> endpoint.Endpoint:
    """
    Construct FHIR Endpoint containing links to either the DICOM study or series.

    :param type: Where the endpoint will point to.
    :type type: typing.Literal[&quot;study&quot;, &quot;series&quot;]
    :param business_id: Business ID
    :type business_id: str
    :return: A FHIR Endpoint.
    :rtype: endpoint.Endpoint
    """
    business_id_as_dcm_uid = conversion_util.from_uuid_dcm_uid(business_id)
    study_uid = f"2.25.{business_id_as_dcm_uid}"
    url_with_attr = DICOM_WEB_URL + f"/studies/{study_uid}/"
    if type == "series":
        url_with_attr += f"series/{study_uid}.1/"
    
    def _construct_connection_type():
        #cc = codeableconcept.CodeableConcept()
        #cc.coding = []
        c = coding.Coding()
        c.system = "http://terminology.hl7.org/CodeSystem/endpoint-connection-type"
        c.code = "dicom-wado-rs"
        #cc.coding.append(c)
        #return cc
        return c

    def _construct_payload_type():
        # only mandatory upon R4B, R5 does not force usage
        # no existing code really fits here, so just a text is set 
        cc = codeableconcept.CodeableConcept()
        cc.text = "DICOM WADO-RS"
        return cc
    
    ep = endpoint.Endpoint(
        status="active",
        connectionType=_construct_connection_type(),
        payloadType=[_construct_payload_type()],
        address=url_with_attr
    )
    ep.id = type
    return ep

def send_to_fhir(path_to_dcm_folder: str, business_id: str, header_with_auth: dict[str, str]) -> str:
    """
    Send generated DICOM files to the FHIR server by converting/wrapping it in an ImagingStudy.

    :param path_to_dcm_folder: Path where the DICOM files exist on the system.
    :type path_to_dcm_folder: str
    :param business_id: Business ID of the DICOM study.
    :type business_id: str
    :param header_with_auth: Header containing the bearer token.
    :type header_with_auth: dict[str, str]
    :return: The business id for the patient.
    :rtype: str
    """

    # TODO: re-reading all the files... poor performance probably
    ds_list = []
    for dcm_file in os.scandir(path_to_dcm_folder):
        if os.path.isfile(dcm_file):
            ds_list.append(pydicom.dcmread(dcm_file))
    
    pat_id = ds_list[0].PatientID
    patient_reference = fhir_handler.patient_already_exists(f"urn:uuid:{pat_id}", header_with_auth)
    if not patient_reference:
        fhir_patient = fhir_handler.construct_fhir_patient(ds_list[0])
        patient_reference = fhir_handler.upload_patient(fhir_patient, header_with_auth)
    fhir_imaging_study = fhir_handler.construct_fhir_imaging_study(business_id, fhir_patient_reference_path=patient_reference ,ds_list=ds_list)
    fhir_handler.upload_imaging_study(fhir_imaging_study, header_with_auth)
    return pat_id