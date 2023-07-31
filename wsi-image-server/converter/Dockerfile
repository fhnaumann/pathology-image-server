FROM python:3.10

RUN apt-get update
RUN apt-get -y install openslide-tools libopenslide0 libturbojpeg0-dev
RUN pip install numpy==1.24.3 psycopg2 watchdog wsidicomizer[openslide] wsidicom pydicom==2.3.1 fhir-resources openslide-python pika python-keycloak

COPY data app
WORKDIR /app


# RUN mkdir dummy-create-data
# COPY example_data dummy-create-data
# RUN cd dummy-create-data && tar -czvf "CMU-1.tar.gz" "Generic CMU-1.tiff" && cd ..

# RUN mkdir -p app/create-data

# WORKDIR /app

# create tarball: tar -czvf <uuid>.tar.gz <path>
# extract tarball: tar -xzvf <uuid>.tar.gz -C <folder>
#

# ENTRYPOINT ["tail", "-f", "/dev/null"]