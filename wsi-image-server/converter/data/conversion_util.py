import uuid

def from_uuid_dcm_uid(uuid_str: str) -> str:
    """
    Convert a UUID to a DICOM UID.
    The UUID (32 characters (36 with dashes)) will be transformed into a number (39 characters/digits).
    Essentially it converts from base 16 to base 10.

    :param uuid_str: A UUID (e.g. "61ec173e-e818-4e3e-96fd-263aaa2d086a") as a string.
    :type uuid_str: str
    :return: A DICOM UID (e.g. "130160969129147924862197661322256910442")
    :rtype: str
    """
    return str(uuid.UUID(f"{{{uuid_str}}}").int)

def from_dcm_uid_to_uuid(dcm_uid_str: str) -> str:
    """
    Convert a DICOM UID to a UUID.
    The DICOM UID (39 characters/digits) will be transformed into a hex-string (32 characters (36 with dashes))-
    Essentially it converts from base 10 to base 16.

    :param dcm_uid_str: A DICOM UID (e.g. "130160969129147924862197661322256910442")
    :type dcm_uid_str: str
    :return: A UUID (e.g. "61ec173e-e818-4e3e-96fd-263aaa2d086a") as a string.
    :rtype: str
    """
    return str(uuid.UUID(int=int(dcm_uid_str)))