import base64
import requests
from fhir.resources.documentreference import DocumentReference, DocumentReferenceContent
from fhir.resources.attachment import Attachment

# with open("example_data/Hamamatsu VMS.zip", "rb") as fin, open("output_encoded.zip.b64", "wb") as fout:
#     base64.encode(fin, fout)
# with open("example_data/test_compress.tar.gz", "rb") as fin:
#     # base64.encode(fin, fout)
#     file_as_b64 = base64.b64encode(fin.read())
#     file_as_b64_as_str = file_as_b64.decode()
#     with open("example_data/output_b64_encoded.txt", "w") as text_file:
#         text_file.write(file_as_b64_as_str)
#         text_file.close()
#     test = b"ABCDE"
#     test_b64 = base64.b64encode(test)
#     test_b64_str = test_b64.decode()
#     json_str = \
#     """
#     {
#         "resourceType": "DocumentReference",
#         "status": "current",
#         "content": [{
#             "attachment": {
#                 "contentType": "application/gzip",
#                 "data": "%s"
#             }
#         }]
#     }
#     """ % file_as_b64_as_str
#     # print(json_str)
#     dr = DocumentReference.parse_raw(json_str)

#     ref_server = "http://localhost:8000/fhir/DocumentReference"
#     r_type = "DocumentReference"
#     headers = {
#         "Accept":"application/fhir+json",
#         "Content-Type":"application/fhir+json"
#     }

#     print(json_str[-100:])
#     response = requests.post(url=ref_server, headers=headers, data=json_str)
#     response.raise_for_status()
#     return_str = response.json()
#     print(response.text)
json_str = \
"""
{
    "resourceType": "DocumentReference",
    "status": "current",
    "content": [{
        "attachment": {
            "contentType": "application/gzip",
            "data": "%s"
        }
    }]
}
""" % base64.b64encode(b"abc").decode('utf-8')
# print(json_str)
dr = DocumentReference.parse_raw(json_str)

ref_server = "http://localhost:8080/fhir/DocumentReference"
r_type = "DocumentReference"
headers = {
    "Accept":"application/fhir+json",
    "Content-Type":"application/fhir+json"
}

print(json_str[-100:])
response = requests.post(url=ref_server, headers=headers, data=json_str)
response.raise_for_status()
return_str = response.json()
print(response.text)


