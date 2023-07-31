FROM maven:3.8-openjdk-17-slim as build-hapi
WORKDIR /tmp/hapi-fhir-jpaserver-starter

ARG OPENTELEMETRY_JAVA_AGENT_VERSION=1.17.0
RUN curl -LSsO https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v${OPENTELEMETRY_JAVA_AGENT_VERSION}/opentelemetry-javaagent.jar

COPY pom.xml .
COPY server.xml .
RUN mvn -ntp dependency:go-offline

COPY src/ /tmp/hapi-fhir-jpaserver-starter/src/
RUN mvn clean install -DskipTests -Djdk.lang.Process.launchMechanism=vfork

FROM build-hapi AS build-distroless
RUN mvn package spring-boot:repackage -Pboot
RUN mkdir /app && cp /tmp/hapi-fhir-jpaserver-starter/target/ROOT.war /app/main.war


########### bitnami tomcat version is suitable for debugging and comes with a shell
########### it can be built using eg. `docker build --target tomcat .`
# FROM bitnami/tomcat:9.0 as tomcat
FROM bitnami/tomcat:9.0 as default

RUN rm -rf /opt/bitnami/tomcat/webapps/ROOT && \
    mkdir -p /opt/bitnami/hapi/data/hapi/lucenefiles && \
    chmod 775 /opt/bitnami/hapi/data/hapi/lucenefiles

USER root
RUN mkdir -p /target && chown -R 1001:1001 target
RUN mkdir /app/create-data
RUN chmod -R a+rw /app/create-data
# COPY setenv.sh $CATALINA_HOME/bin/setenv.sh
# RUN chmod +x $CATALINA_HOME/bin/setenv.sh
# USER 1001

COPY --chown=1001:1001 catalina.properties /opt/bitnami/tomcat/conf/catalina.properties
COPY --chown=1001:1001 server.xml /opt/bitnami/tomcat/conf/server.xml
COPY --chown=1001:1001 setenv.sh /opt/bitnami/tomcat/bin/setenv.sh
COPY --from=build-hapi --chown=1001:1001 /tmp/hapi-fhir-jpaserver-starter/target/ROOT.war /opt/bitnami/tomcat/webapps/ROOT.war
COPY --from=build-hapi --chown=1001:1001 /tmp/hapi-fhir-jpaserver-starter/opentelemetry-javaagent.jar /app

WORKDIR /app

ENV ALLOW_EMPTY_PASSWORD=yes
# ENTRYPOINT ["java", "-Xmx14g", "--class-path", "/app/main.war", "-Dloader.path=main.war!/WEB-INF/classes/,main.war!/WEB-INF/,/app/extra-classes", "org.springframework.boot.loader.PropertiesLauncher", "app/main.war"]

########### distroless brings focus on security and runs on plain spring boot - this is the default image
# FROM gcr.io/distroless/java17-debian11:nonroot as default2
# # 65532 is the nonroot user's uid
# # used here instead of the name to allow Kubernetes to easily detect that the container
# # is running as a non-root (uid != 0) user.
# USER 65532:65532
# WORKDIR /app

# COPY --chown=nonroot:nonroot --from=build-distroless /app /app
# COPY --chown=nonroot:nonroot --from=build-hapi /tmp/hapi-fhir-jpaserver-starter/opentelemetry-javaagent.jar /app

# ENTRYPOINT ["java", "-Xmx6g", "--class-path", "/app/main.war", "-Dloader.path=main.war!/WEB-INF/classes/,main.war!/WEB-INF/,/app/extra-classes", "org.springframework.boot.loader.PropertiesLauncher", "app/main.war"]
