import os

def format_exception(exception: Exception) -> str:
    """
    Formats an exception, which may include other exceptions (using the "raise X from Y" mechanic) into
    a single string. It strips the stacktrace pointing to the code lines causing the errors and only
    includes the error messages from each exception contained.

    :param exception: The outer-most exception which occurred.
    :type exception: Exception
    :return: A string representation of the exceptions.
    :rtype: str
    """
    if not exception.__cause__:
        return repr(exception)
    else:
        return f"{repr(exception)} caused by {os.linesep}{format_exception(exception.__cause__)}"

class ConverterConstructionException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class DicomTagKeyIsMissingException(Exception):
    pass

class WsiTarballExtractionException(Exception):
    pass

class WsiDicomizerConversionException(Exception):
    pass

class InvalidTagNameException(Exception):
    pass

class MandatoryTagIsMissing(Exception):
    pass

class UploadToPacsException(Exception):
    pass

class UploadToFHIRException(Exception):
    pass

class GrantKeycloakRoleException(Exception):
    pass