FROM quay.io/keycloak/keycloak:21.1.1 as builder

#ENV KC_HEALTH_ENABLED=true
#ENV KC_METRICS_ENABLED=true

ENV KC_DB=postgres

WORKDIR /opt/keycloak
RUN keytool -genkeypair -storepass password -storetype PKCS12 -keyalg RSA -keysize 2048 -dname "CN=server" -alias server -ext "SAN:c=DNS:localhost,IP:127.0.0.1" -keystore conf/server.keystore
RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:21.1.1

COPY --from=builder /opt/keycloak/ /opt/keycloak/

ENV KC_DB_URL=jdbc:postgresql://keycloak-postgres:5432/keycloak
ENV KC_DB_USERNAME=admin
ENV KC_DB_PASSWORD=admin
ENV KC_PROXY=edge
# ENV KC_HOSTNAME=keycloak-postgres

# COPY keycloak.conf /conf/keycloak.conf
