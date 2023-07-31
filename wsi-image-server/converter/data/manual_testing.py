import converter
import sender
import uuid

fake_json_body = \
    """
    {
        "uuid": "%s",
        "path_to_wsi_tarball": "./dummy-create-data/CMU-1.tar.gz",
        "path_in_tarball_for_openslide": "Generic CMU-1.tiff",
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
    """ % str(uuid.uuid4())
conv = converter.Converter.fromBroker(fake_json_body.encode())
business_id, path_to_dcm_folder = conv.handle()
sender.send_and_cleanup(business_id, path_to_dcm_folder)
while True:
    pass