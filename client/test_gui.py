import PySimpleGUI as sg
import requests
import os.path
from keycloak import KeycloakOpenID
import json
from fhir.resources.R4B.documentreference import DocumentReference, DocumentReferenceContent
from fhir.resources.R4B.attachment import Attachment
from fhir.resources.R4B.extension import Extension
from fhir.resources.R4B.imagingstudy import ImagingStudy, ImagingStudySeries, ImagingStudySeriesInstance
from fhir.resources.R4B.endpoint import Endpoint
from typing import Literal
import base64
import shutil
from pathlib import Path
import threading
import concurrent.futures
import psycopg2
from requests.auth import HTTPBasicAuth
import time
import random
import string
from faker import Faker

FHIR_PORT = 8081
FHIR_BASE_URL = f"http://localhost:{FHIR_PORT}/fhir"
FHIR_DOCUMENT_REFERENCE_URL = f"{FHIR_BASE_URL}/DocumentReference"
FHIR_IMAGING_STUDY_URL = f"{FHIR_BASE_URL}/ImagingStudy"

POSTGRES_REST_PORT = 3001
POSTGRES_REST_BASE_URL = f"http://localhost:{POSTGRES_REST_PORT}"

USER_NAME = "user"
USER_PASSWORD = "user"

MAX_TAGS_COUNT = 10

# key: Tarball Name (used to locate file)
# value: tuple with the folder inside the tarball and the filename. Together they form the path inside the tarball.
VALID_TARBALLS = {
    "Aperiori CMU-1-JP2K-33005.tar.gz": ("Aperiori CMU-1-JP2K-33005", "Aperiori CMU-1-JP2K-33005.svs"),
    "Generic CMU-1.tar.gz": ("Generic CMU-1", "Generic CMU-1.tiff"),
    "Hamamatsu NDPI.tar.gz": ("Hamamatsu NDPI", "Hamamatsu NDPI CMU-1.tiff"),
    "Hamamatsu VMS.tar.gz": ("Hamamatsu VMS", "CMU-1-40x - 2010-01-12 13.24.05.vms"),
    "Leica SCN.tar.gz": ("Leica SCN", "Leica-1 SCN.tiff"),
    "MIRAX CMU-1.tar.gz": ("MIRAX CMU-1", "CMU-1.mrxs"),
    "Olympus VSI OS-1.tar.gz": ("Olympus VSI OS-1", "OS-1.vsi"),
    "Trestle TIFF CMU-1.tar.gz": ("Trestle TIFF CMU-1", "CMU-1.tif"), # will not work
    "Ventana.tar.gz": ("Ventana", "Ventana-1.tiff")
}

# sg.theme_previewer()
sg.theme("LightBrown6")


# First the window layout in 2 columns
file_list_column = [
    [
        sg.Text("Image Folder"),
        sg.In(size=(25, 1), enable_events=True, key="-FOLDER-"),
        sg.FolderBrowse(),
    ],
    [
        sg.Listbox(
            values=[], enable_events=True, size=(45, 20), key="-FILE LIST-"
        )
    ],
    *[[sg.Text("Tag:"), sg.InputText(size=(15, 1), key=f"-TAG {i}-"), sg.Text("Value:"), sg.InputText(size=(15,1), key=f"-VALUE {i}-")] for i in range(MAX_TAGS_COUNT)],
    [
        sg.Text("Username:"), sg.InputText(size=(15, 1), default_text=USER_NAME, key="-USERNAME-")
    ],
    [
        sg.Text("Password:"), sg.InputText(size=(15, 1), default_text=USER_PASSWORD, key="-USERPASSWORD-")
    ],
    [
        sg.Text("IP:"), sg.InputText(default_text=FHIR_BASE_URL, size=(25, 10), key="-IP-")
    ],
    [
        sg.Submit(button_text="Send", size=(40, 1), disabled=True, key="-SEND-")
    ]
]

status_column = [
    [sg.Text("Status:")],
    [sg.Multiline(size=(40,20), key="-STATUS-", autoscroll=True, auto_refresh=True, disabled=True)],
]

image_column = [
    [sg.InputText(default_text="", size=(30,1), enable_events=True, key="-MANUAL BUSINESS ID-")],
    [
        sg.Text("Instance:"), sg.InputText(size=(15, 1), default_text="0", key="-INSTANCE-"), sg.Text("/ ?", key="-TOTAL INSTANCE-")
    ],
    [
        sg.Text("Frame:"), sg.InputText(size=(15, 1), default_text="1", key="-FRAME-"), sg.Text("/ ?", key="-TOTAL FRAME-")
    ],
    [
        sg.Text("Username:"), sg.InputText(size=(15, 1), default_text=USER_NAME, key="-USERNAME2-")
    ],
    [
        sg.Text("Password:"), sg.InputText(size=(15, 1), default_text=USER_PASSWORD, key="-USERPASSWORD2-")
    ],
    [sg.Button("Use business ID to render level", size=(25,1), disabled=True, key="-USE BUSINESS ID-")],
    [sg.Image(key="-IMAGE-")]
]

# ----- Full layout -----
layout = [
    [
        sg.Column(file_list_column, vertical_alignment="top"),
        sg.VSeperator(),
        sg.Column(status_column, vertical_alignment="top"),
        sg.VSeparator(),
        sg.Column(image_column, vertical_alignment="top")
    ]
]
window = sg.Window("Image Viewer", layout)

def create_tarball(path_to_file: str, filename: str, status_box) -> str:
    shutil.make_archive(base_name=filename, root_dir=path_to_file, base_dir=".", format="gztar")
    status_box.print("Created tarball.")
    return os.path.join(path_to_file, filename + ".tar.gz")

def b_64_encode_file_(filename: str) -> str:
    with open(filename, "rb") as f:
        file_as_b64 = base64.b64encode(f.read())
        file_as_b64_as_str = file_as_b64.decode()
        return file_as_b64_as_str

def create_document_reference(file_as_b64_as_str: str, path_in_tarball: str, additional_dcm_tags: dict[str, str]) -> DocumentReference:
    def create_dr_content(file_as_b64_as_str: str) -> DocumentReferenceContent:
        content = DocumentReferenceContent(
            attachment=Attachment(contentType="application/gzip", data=file_as_b64_as_str),
        )
        return content
    
    def create_dcm_tag_value_extension(tag:str, value: str) -> Extension:
        ext = Extension(
            url="https://localhost:8080/fhir/StructureDefinition/DicomTag",
            extension=[
                Extension(url="dcm_key", valueString=tag),
                Extension(url="dcm_value", valueString=value)
            ]
        )
        return ext
    
    def create_path_in_tarball_extension(path_in_tarball: str) -> Extension:
        return Extension(url="https://localhost:8080/fhir/StructureDefinition/PathInTarball", valueString=path_in_tarball)

    dr = DocumentReference(
        status="current",
        content=[create_dr_content(file_as_b64_as_str)]
    )
    dr.extension = [
        create_path_in_tarball_extension(path_in_tarball),
        *[create_dcm_tag_value_extension(key, value) for key, value in additional_dcm_tags.items()]
    ]
    return dr

def get_address_for(what_for: Literal["study", "series"], endpoints: list[Endpoint]) -> str:
    for endpoint in endpoints:
        if what_for == endpoint.id:
            return endpoint.address
    raise RuntimeError("imaging study has no wado-rs series endpoint!")

def get_dicom_study_uid_identifier(identifiers: list[dict[str, str]]) -> str:
    for identifier in identifiers:
        if identifier["system"] == "urn:dicom:uid":
            return identifier["value"].replace("urn:oid:")
    raise RuntimeError("no dicom identifier in imaging study!")

def get_sop_instance(series: ImagingStudySeries, instance_number_to_find=0) -> ImagingStudySeriesInstance:
    if instance_number_to_find < 0:
        largest_instance  = (None, 0)
        instance: ImagingStudySeriesInstance
        for instance in series.instance: #type: ImagingStudySeriesInstance
            if instance.number >= largest_instance[1]:
                largest_instance = (instance, instance.number)
        return largest_instance[0]
    else:
        instance: ImagingStudySeriesInstance
        for instance in series.instance: #type: ImagingStudySeriesInstance
            if instance.number == instance_number_to_find:
                return instance
    raise RuntimeError(f"no sop instance with number {instance_number_to_find} exists in series!")

def generate_random_dcm_values():
    dcm_tags = ["PatientID", "PatientName", "PatientAge", "PatientBirthDate", "PatientSex"]
    fake = Faker()
    # 19930822
    return {
        "PatientID": ''.join(random.choices(string.ascii_uppercase + string.digits, k=5)),
        "PatientName": fake.name(),
        "PatientAge": f"0{random.randint(10, 99)}Y",
        "PatientBirthDate": f"{random.randint(1930, 2010)}0{random.randint(1, 9)}{random.randint(10, 28)}",
        "PatientSex": random.choice(["M", "F", "O"])
    }
    


selected_folder = ""
selected_file_name = ""
access_token = None
# Run the Event Loop
while True:
    event, values = window.read()
    if event == "Exit" or event == sg.WIN_CLOSED:
        break
    # Folder name was filled in, make a list of files in the folder
    if event == "-FOLDER-":
        selected_folder = values["-FOLDER-"]
        try:
            # Get list of files in folder
            file_list = os.listdir(selected_folder)
        except:
            file_list = []
        fnames = [
            # f if os.path.isfile(os.path.join(selected_folder, f)) else f"{f} (Folder)" for f in file_list
            # f for f in file_list if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith((".png", ".gif"))
        ]
        window["-FILE LIST-"].update(file_list)
    elif event == "-FILE LIST-":  # A file was chosen from the listbox
        
        selection = values[event]
        if selection:
            #selected_file_name = Path(selection[0]).with_suffix("")
            selected_file_name = selection[0]
            print(selected_file_name)
            index = window["-FILE LIST-"].get_indexes()[0]
            window["-SEND-"].update(disabled=False)
            
            random_tags = generate_random_dcm_values()
            for idx, (tag, value) in enumerate(random_tags.items()):
                window[f"-TAG {idx}-"].update(value=tag)
                window[f"-VALUE {idx}-"].update(value=value)

        try:
            filename = os.path.join(
                values["-FOLDER-"], values["-FILE LIST-"][0]
            )
        except:
            pass
    elif event == "-SEND-": # initiate sending to fhir server

        window["-STATUS-"].update("") # clear status box
        window["-MANUAL BUSINESS ID-"].update("") # clear input field for uuid
        window["-IMAGE-"].update("")

        def _dcm_tags_as_dict(values):
            dcm_tags = {}
            for i in range(MAX_TAGS_COUNT):
                key = values[f"-TAG {i}-"]
                value = values[f"-VALUE {i}-"]
                if key != "":
                    dcm_tags[key] = value
            return dcm_tags


        print("selected:", selected_file_name)
        print("folder", selected_folder)
        window["-STATUS-"].print("Creating tarball...")
        #thread = threading.Thread(target=create_tarball, args=[selected_folder, selected_file_name, window["-STATUS-"]])
        #thread.start()
        # create_tarball(path_to_file=selected_folder, filename=selected_file_name, status_box=window["-STATUS-"])
        window["-STATUS-"].print("Creating DocumentReference from given tags...")
        dr = create_document_reference(file_as_b64_as_str=b_64_encode_file_(os.path.join("example_data", "tarballs", selected_file_name)),
                                             path_in_tarball="/".join(VALID_TARBALLS[selected_file_name]),
                                             additional_dcm_tags=_dcm_tags_as_dict(values))
        window["-STATUS-"].print("Created DocumentReference.")
        window["-STATUS-"].print("Connecting to Keycloak for token...")
        keycloak_openid = KeycloakOpenID(
        server_url="http://localhost:8085",
        client_id="myclient",
        realm_name="myrealm",
        client_secret_key="myclient-secret"
        )

        try:
            token: dict = keycloak_openid.token(
                username=values["-USERNAME-"],
                password=values["-USERPASSWORD-"]
            )
        except Exception as e:
            sg.popup_error_with_traceback(f"Invalid Keycloak credentials!", e)
            continue
        access_token = token["access_token"]
        window["-STATUS-"].print("Received new access token.")
        header_with_auth = {
            "Accept":"application/fhir+json",
            "Content-Type":"application/fhir+json",
            "Authorization": f"Bearer {access_token}"
        }
        url = values["-IP-"]
        window["-STATUS-"].print(f"Preparing sending DocumentReference to {url}.")
        response = requests.post(url=FHIR_DOCUMENT_REFERENCE_URL, headers=header_with_auth, data=dr.json())
        try:
            response.raise_for_status()
        except Exception as e:
            sg.popup_error_with_traceback(f"Not enough permission to create resources!", e)
            print(response.text)
            response_json = response.json()
            print(json.dumps(response_json, indent=4))
            continue
        print(response.text)
        response_json = response.json()
        business_id = response_json["issue"][0]["details"]["coding"][0]["code"].replace("urn:uuid:", "")
        print(business_id)
        window["-STATUS-"].print(f"Sent DocumentReference to {url}.")
        window["-STATUS-"].print(f"Received ID: \"{business_id}\"")
        while True:
            window["-STATUS-"].print("Fetching information from db in 5 seconds...")
            time.sleep(5)
            try:
                conn = psycopg2.connect(
                    host="localhost", # container name change-me
                    port="5433", # port defined in docker-compose.yml change-me
                    database="prop", # defined in db.sql in prop folder change-me
                    user="postgres", # defined in environment variables for prop-postgres container secret-me
                    password="postgres" # defined in environment variables for prop-postgres container secret-me
                )
                cur = conn.cursor()
                sql = \
                    """
                    SELECT converted,error_msg
                    FROM data
                    WHERE id=%s::UUID
                    """
                cur.execute(sql, (business_id,))
                converted, error_msg = cur.fetchone()
                if not converted and (error_msg is None or error_msg) == "":
                    window["-STATUS-"].print("Not converted yet...")
                    continue
                if converted:
                    window["-STATUS-"].print("Successfully converted to DICOM WSI.")
                    break
                else:
                    window["-STATUS-"].print(f"Error while converting: {error_msg}")
                    break
            except Exception as e:
                print(e)
                print("error db")
                break
        window["-MANUAL BUSINESS ID-"].update(value=business_id)
        window["-USE BUSINESS ID-"].update(disabled=False)


    elif event == "-MANUAL BUSINESS ID-":
        business_id = values["-MANUAL BUSINESS ID-"]
        if business_id is not None and business_id != "":
            window["-USE BUSINESS ID-"].update(disabled=False)
    elif event == "-USE BUSINESS ID-":

        url = f"{FHIR_IMAGING_STUDY_URL}?identifier=urn:uuid:{values['-MANUAL BUSINESS ID-']}"
        print("url", url)
        window["-STATUS-"].print("Connecting to Keycloak for token...")
        keycloak_openid = KeycloakOpenID(
        server_url="http://localhost:8085",
        client_id="myclient",
        realm_name="myrealm",
        client_secret_key="myclient-secret"
        )

        try:
            token: dict = keycloak_openid.token(
                username=values["-USERNAME2-"],
                password=values["-USERPASSWORD2-"]
            )
        except Exception as e:
            sg.popup_error_with_traceback(f"Invalid Keycloak credentials!", e)
            continue
        access_token = token["access_token"]
        window["-STATUS-"].print("Received new access token.")
        header_with_auth = {
            "Accept":"application/fhir+json",
            "Content-Type":"application/fhir+json",
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.get(url=url, headers=header_with_auth)
        try:
            response.raise_for_status()
        except Exception as e:
            sg.popup_error_with_traceback(f"Not enough permission read the resource associated with the ID '{business_id}'!", e)
            print(response.text)
            response_json = response.json()
            continue
            #print(json.dumps(response_json, indent=4))
        # print(response.text)
        return_str = response.json()
        print(return_str)
        if "entry" not in return_str:
            print("missing entry")
            continue
            raise RuntimeError("entry is not in return json")
        entries = return_str["entry"]
        if len(entries) == 0:
            raise RuntimeError("no entries exist (possibly wrong authentication/not refreshed authentication?)")
        if len(entries) > 1:
            print("Warning: More that one entry exists for this business id, should never be the case!")
        entry = entries[0]
        resource = entry["resource"]

        imaging_study = ImagingStudy.parse_obj(resource)

        sop_instance_amount = imaging_study.numberOfInstances - 1 # 0 indexed!
        window["-TOTAL INSTANCE-"].update(f"/ {sop_instance_amount}") 

        series: ImagingStudySeries = imaging_study.series[0]
        try:
            sop_instance = get_sop_instance(series, instance_number_to_find=int(values["-INSTANCE-"]))
        except Exception as e:
            sg.popup_error_with_traceback(f"Malformed input sent to the DICOMweb server!", e)
            continue

        series_url = get_address_for(what_for="series", endpoints=imaging_study.contained)

        width_tag = "00480006"
        height_tag = "00480007"
        number_of_frames_tag = "00280008"
        url_to_get_first_instance_sizes = f"{series_url}/instances?SOPInstanceUID={sop_instance.uid}&includefield={width_tag}&includefield={height_tag}&includefield={number_of_frames_tag}"
        url_to_get_first_instance_sizes = url_to_get_first_instance_sizes.replace("orthanc-pacs", "localhost") # not in container
        response = requests.get(url=url_to_get_first_instance_sizes, headers={"Authorization": f"Bearer {access_token}"})
        try:
            response.raise_for_status()
        except:
            print(response.text)
        return_str = response.json()
        print(return_str)
        image_width = return_str[0][width_tag]["Value"][0]
        image_height = return_str[0][height_tag]["Value"][0]
        number_of_frames = return_str[0][number_of_frames_tag]["Value"][0]
        print(image_width)
        print(image_height)
        print(number_of_frames)
        window["-TOTAL FRAME-"].update(f"/ {number_of_frames}")
        frame_number = values["-FRAME-"]
        url_to_rendered_first_instance = f"{series_url}instances/{sop_instance.uid}/frames/{frame_number}/rendered?viewport=,,,,{image_width},{image_height}"
        # url_to_rendered_first_instance = f"{series_url}instances/{sop_instance.uid}/frames/{frame_number}/rendered"
        url_to_rendered_first_instance = url_to_rendered_first_instance.replace("orthanc-pacs", "localhost") # not in container
        print(url_to_rendered_first_instance)
        headers = {
            "Accept": "image/png",
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.get(url=url_to_rendered_first_instance, headers=headers, stream=True)
        try:
            response.raise_for_status()
        except Exception as e:
            print("error while get")
            print(response.status_code)
            print(response.text)
            sg.popup_error_with_traceback(f"Malformed input sent to the DICOMweb server!", e)
        rendered_image_filename = os.path.join("fetched_images", sop_instance.uid.replace(".", "_") + ".png")
        with open(rendered_image_filename, "wb") as file:
            # response.raw.decode_content = False
            file.write(response.content)
        window["-IMAGE-"].update(filename=rendered_image_filename)
window.close()