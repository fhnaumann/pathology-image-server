import uuid

def from_uuid_dcm_uid(uuid_str: str) -> str:
    return str(uuid.UUID(f"{{{uuid_str}}}").int)

def from_dcm_uid_to_uuid(dcm_uid_str: str) -> str:
    return str(uuid.UUID(int=int(dcm_uid_str)))