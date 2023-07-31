from __future__ import annotations
from wsidicomizer import WsiDicomizer
from pathlib import Path
import filler
import json
import os
import shutil
import logging
import exceptions
from keycloak_info import KeycloakInfo
from pydicom.datadict import keyword_for_tag

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s", datefmt="%d/%b/%Y %H:%M:%S")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Converter():
    """
    Handles the conversion from proprietary files to dicom files using the wsidicomizer library 
    (which interally uses wsidicom and OpenSlide).
    """
    def __init__(self, business_id: str, path_to_wsi_tarball: str, path_in_tarball_for_openslide: str, dicom_tags: dict[str, str]) -> None:
        """
        Creates a new converter object. Most commonly created through the static `fromBroker` method.

        A temporary folder at `./temp_data/` will be created to temporarily to store the extracted tarball and the converted
        dicom files before they are uploaded. The extracted tarball will be placed at `./temp_data/<uuid>/` and the dicom
        files will be placed at `./temp_data/<uuid>/dicom/`.
        
        Once they are uploaded and confirmed by the PACS (done by another python script),
        they will be deleted, although that is the responsibility of the other script.

        Parameters
        ----------
        business_id : str
            The UUID assigned to the wsi file when it was initially received. The UUID can be found as the file name in the
            flat file storage and as the primary key in the proprietary database. In this case it was probably sent through
            the message broker in the `uuid` field in the sent json.
        path_to_wsi_tarball : str
            The path to the proprietary file as a tarball (.tar.gz extension). The path will be somewhere in the shared volume between
            this converter container and the proprietary file storage container (e.g. create-data/<uuid>.tar.gz).
        path_in_tarball_for_openslide : str
            The path/filename supplied to openslide for recognizing the proprietary file. In the cases where the tarball contains exactly
            one file, this will be the filename and extension (e.g. 'Generic CMU-1.tiff'). However in some cases the tarball contains a folder,
            e.g. for proprietary files like Hamamatsu VMS. For this example this variable would then be the path to the .vms file.
            For future improvements: This variable could be optional if after extraction this script would search for all known extension and do
            a best-effort opening with OpenSlide.
        dicom_tags : dict[str, str]
            The additional supplied dicom tags which will be set in the converted dicom files.
            The key is the dicom tag as hexnumbers formatted with a ',' so for example: "(0010,0010)".
            The value is the dicom value as a string. As of now only fields with string types can be set (no automatic casting to other types is done).
        """
        self.business_id: str = business_id
        # The path usually is "./app/create-data/<uuid>.tar.gz" and the outer parent folder "/app/" is not needed,
        # as the scripts running in this container are already located in the "/app" folder. Therefore remove this folder from the
        # path and only keep "create-data/<uuid>.tar.gz"
        path_object = Path(path_to_wsi_tarball)
        self._path_to_wsi_tarball: str = path_object.relative_to(*path_object.parts[:1])
        self._path_in_tarball_for_openslide: str = path_in_tarball_for_openslide
        self._output_folder_path: str = f"temp_data/{business_id}/dicom"
        self.dcm_tags: dict[str, str] = dicom_tags
        Path(self._output_folder_path).mkdir(parents=True, exist_ok=True)
        logger.info("Created folder (and potential subfolder) %s", self._output_folder_path)

    @staticmethod
    def fromBroker(data) -> tuple[Converter, KeycloakInfo]:
        """
        Entry point for when a converter is needed. It takes the json message and creates a Converter object with the necessary data.

        :param jsonMessage: The json message received from the message broker.
        :type jsonMessage: str
        :return: A converter object where the `handle()` method may be invoked to start the conversion process.
        :rtype: Converter
        """
        try:
            logger.debug("Received json message %s", data)
            business_id: str = data["uuid"]
            keycloak_user_id: str = data["keycloak_user_id"]
            path_to_wsi_tarball: str = data["path_to_wsi_tarball"]
            path_in_tarball_for_openslide: str = data["path_in_tarball_for_openslide"]
            dicom_tags: dict[str, str] = Converter._convert_json_dcm_tags_2_dict(data["tags"])
            logger.debug("Business ID: %s\n \
                        Keycloak User ID: %s\n \
                        Path to WSI Tarball: %s\n \
                        Path in Tarball for OpsenSlide: %s\n \
                        Dicom Tags: %s", \
                        business_id, keycloak_user_id, path_to_wsi_tarball, path_in_tarball_for_openslide, dicom_tags)
            return Converter(business_id, path_to_wsi_tarball, path_in_tarball_for_openslide, dicom_tags), KeycloakInfo(user_id=keycloak_user_id)
        except Exception as e:
            logger.error("Error occurred while extracting data from rabbitmq %s", e)
            raise exceptions.ConverterConstructionException from e

    def handle(self) -> tuple[str, str]:
        """
        Entry point for starting the conversion once a Converter object was created.

        The following steps will be done:
        1. Uncompress the tarball file
        2. Start the conversion to dicom files
        3. Fill in supplied dicom tags
        4. Validate that no tags, which are deemed as necessary, are missing

        NOTE: The generated files won't be deleted as they are not uploaded yet. Deleting the files once
        the dicom files are uploaded is in the responsibility of the uploading script.
        :return: The path to the dicom files (`./temp_data/<uuid>/dicom/)`.
        :rtype: str
        """
        self.uncompress_file(self._path_to_wsi_tarball)
        converted_files: list[str] = self.convert()
        dataset = filler.fill_default_metadata_and_dcm_tags(converted_files, self.business_id, self.dcm_tags)
        missing_tags = filler.validate_no_missing_mandatory_tags(dataset)
        if missing_tags:
            missing_tags = [keyword_for_tag(tag) for tag in missing_tags] # human readable tag names
            logger.warning("Some mandatory DICOM tags are missing: %s", missing_tags)
            raise exceptions.MandatoryTagIsMissing(f"Some mandatory tags are missing: {missing_tags}!")
        else:
            logger.info("All necessary DICOM tags are provided.")
        return self.business_id, self._output_folder_path
    
    @staticmethod
    def _convert_json_dcm_tags_2_dict(json_dcm_tags: list[dict[str, str]]) -> dict[str, str]:
        """
        Converts the dicom tags passed through the message broker in json to a python dict.

        Example:

        .. code-block:: json
        {
            "tags": [
                {
                    "key": "0010,0010",
                    "value": "Peter"
                },
                {
                    "key": "0010,0020",
                    "value": "5"
                }
            ]
        }

        The json above will be converted into the following python dict:

        .. code-block:: json
        {
            "0010,0010": "Peter",

            "0010,0020": "5"
        }

        Parameters
        ----------
        json_dcm_tags : list[dict[str, str]]
            _description_

        Returns
        -------
        dict[str, str]
            _description_
        """
        dcm_tags_as_dict = {}
        for kv_pair in json_dcm_tags:
            try: 
                key = kv_pair["key"]
                value = kv_pair["value"]
                dcm_tags_as_dict[key] = value
                logger.debug("Found DICOM tag: key=%s, value=%s", key, value)
            except KeyError as e:
                logger.warning("Invalid format for DICOM tag: pair=%s", kv_pair)
                raise exceptions.DicomTagKeyIsMissingException(f"Dicom tag has either missing key or value!") from e
        return dcm_tags_as_dict

    def uncompress_file(self, path_to_wsi_tarball: str) -> None:
        """
        Uncompresses the proprietary tarball file.

        The extracted file/folder will be placed at `./temp_data/<uuid>/`.

        Parameters
        ----------
        path_to_wsi_tarball : str
            The path to the proprietary file as a tarball (.tar.gz extension). The path will be somewhere in the shared volume between
            this converter container and the proprietary file storage container (e.g. create-data/<uuid>.tar.gz).
        """
        try:
            uncompressed_file_path = f"temp_data/{self.business_id}"
            shutil.unpack_archive(filename=path_to_wsi_tarball, extract_dir=uncompressed_file_path, format="gztar")
            self._path_to_wsi_tarball = uncompressed_file_path
            print("path to uncompressed wsi file:", self._path_to_wsi_tarball)
            logger.info("Unpacked file. Can be found at %s", self._path_to_wsi_tarball)
        except ValueError as e:
            logger.exception("Error while extracting tarball from path %s with message: %s", self._path_to_wsi_tarball, e)
            raise exceptions.WsiTarballExtractionException("Tarball cannot be extracted!") from e

    def convert(self) -> list[str]:
        """
        Convert the (extracted) proprietary file to dicom files using the wsidicomizer library.
        The files will be created at `temp_data/<uuid>/dicom/`.

        For the development phase the conversion is skipped if the folder is not empty.
        Returns
        -------
        list[str]
            The filenames of the converted dicom files, NOT including the parent paths.
            The filenames will be their SOPInstanceUIDs.
        """
        path_to_wsi_file = os.path.join(f"temp_data/{self.business_id}", self._path_in_tarball_for_openslide)
        existing_dcm_files = os.listdir(self._output_folder_path)
        if len(existing_dcm_files) > 0:
            logger.warning("Skipping conversion to DICOM as files already exist in the folder (probably for development, should not happen in production!)")
            return [os.path.join(self._output_folder_path, existing_dcm_file) for existing_dcm_file in existing_dcm_files]
        logger.info("Starting conversion...")
        try:
            converted_files = WsiDicomizer.convert(
                filepath=path_to_wsi_file,
                output_path=self._output_folder_path
            )
            logger.info("Converted to WSI DICOM at path %s", self._output_folder_path)
            return converted_files
        except Exception as e:
            logger.error("Error occurred while converting to WSI DICOM %s", e)
            raise exceptions.WsiDicomizerConversionException("wsidicomizer encountered an issue while converting!") from e
