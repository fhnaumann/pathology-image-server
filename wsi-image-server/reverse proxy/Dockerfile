FROM nginx

COPY nginx.conf /etc/nginx/nginx.conf
COPY certs/* /etc/nginx/ssl/localhost/
# RUN mkdir -p /etc/nginx/conf.d/
# COPY nginx.conf /etc/nginx/conf.d/default.conf
# RUN mkdir /etc/nginx/conf.d/test
# COPY test.conf /etc/nginx/conf.d/test/test.conf