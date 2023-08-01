# Pathology Image Server

This project is a proof-of-concept implementation of a pathology whole slide image (WSI) server. It is built using only open-source tools and conforms to the DICOM and FHIR standards.

Proprietary WSI file formats that are uploaded to this server are converted to DICOM and then stored on a PACS server. For easier access some parts of the DICOM metadata are stored in FHIR resources on a FHIR server.

The image below illustrate a general workflow.

<img src="images/general%20architecture.png" alt="general architecture" width="600"/>

Visit the documentation to get more insight about the components used in this project.

## Prerequisites

- Clone/Download this repository
- Docker (with compose file version >= 3)
- A proprietary WSI file archived into a `tar.gz` (see [here](TODO) for details).
- A client that sends a FHIR DocumentReference (see [here](TODO) for details). The client in this repository may be used to do that.

## Configuration

The default configuration uses sample variables for things like account information. Passwords for such accounts are also stored in plain text in the code. Any variable that may change has a `change-me` comment. Any variable that contains sensitive information has a `secret-me` comment. You can search the entire project to find and access all the locations.

## Run

Navigate into the `/wsi-image-server` folder and run the command `docker compose up`. This will start all the necessary Docker containers. Running the command for the first time may take some time (> 10 minutes). Subsequent re-runs should only take up to a minute to start the containers.

Read [here](TODO) what data is created on the first run.
