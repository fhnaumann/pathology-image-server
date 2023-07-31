import orthanc
import pprint
from keycloak.keycloak_openid import KeycloakOpenID
import conversion_util
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s", datefmt="%d/%b/%Y %H:%M:%S")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def is_dicom_web_get_access(url: str, request):
    return "dicom-web" in url

def is_converter_pacs_uploader(url: str, request, roles):
    is_post_request = request["method"] == 2
    return is_post_request and "converter_pacs_upload" in roles

def filter(uri, **request):
    # TODO: REMOVE, ONLY FOR TESTING!!!
    # return True

    headers = request["headers"]

    if "authorization".casefold() not in (header.casefold() for header in headers):
        logger.warning("No bearer token found. Reject access.")
        return False

    kc_openid_client = KeycloakOpenID(
    server_url="http://keycloak:8080", # change-me
    client_id="myclient", # change-me
    client_secret_key="myclient-secret", # secret-me
    realm_name="myrealm" # change-me
    )
    bearer_token = request["headers"]["authorization"].replace("Bearer ", "")

    token_info = kc_openid_client.introspect(bearer_token)
    if not token_info["active"]:
        logger.warning("Token is invalid. Reject access.")
        return False
    roles: list[str] = token_info["realm_access"]["roles"]

    if is_converter_pacs_uploader(uri, request, roles):
        logger.info("Detected that the uploader is the converter. Grant access.")
        return True
    split = uri.split("/")[1:] # ignore empty string because the url starts with '/'
    # 0 -> "dicom-web"
    # 1 -> "studies"
    # 2 -> <StudyInstanceUID>
    # 3 -> "series"
    # 4 -> <SeriesInstanceUID>
    # 5 -> "instances"
    # 6 -> <SOPInstanceUID>
    # 7 -> "frames"
    # 8 -> <frame_number>
    # 9 -> "rendered"
    study_instance_uid = split[2]
    to_remove = "2.25."
    business_id_as_number = study_instance_uid[len(to_remove):] # remove "2.25."

    business_id: str = conversion_util.from_dcm_uid_to_uuid(business_id_as_number)
    if "admin" in roles or f"imaging_study_{business_id}" in roles:
        logger.info("User has approriate roles. Grant access.")
        return True

    logger.warning("User does not have required role to view this study. Reject access.")
    return False  # False to forbid access

orthanc.RegisterIncomingHttpRequestFilter(filter)