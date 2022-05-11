#!/usr/bin/python
# -*- coding:utf-8 -*-
# Filename: pobs_templates.py

def header():
    header = """
#######################
## GENERATED BY POBS ##
#######################
"""
    return header

def footer():
    footer = """
#########
## END ##
#########
"""
    return footer

def s6_installation():
    scripts = """
# install s6-overlay
ADD https://github.com/just-containers/s6-overlay/releases/download/v2.2.0.1/s6-overlay-amd64-installer /tmp/
RUN chmod +x /tmp/s6-overlay-amd64-installer && /tmp/s6-overlay-amd64-installer /
"""
    return scripts

def copy_pobs_files():
    scripts = """
# copy POBS files
COPY ./pobs_files/ /
"""
    return scripts

def set_env():
    scripts = """
# set up environment variables
ENV POBS_SERVICE_NAME=app
ENV POBS_APPLICATION_PACKAGES=
ENV POBS_APM_SERVER=http://172.17.0.1:8200
ENV JAVA_TOOL_OPTIONS "$JAVA_TOOL_OPTIONS -javaagent:/home/elastic/elastic-apm-agent-1.30.1.jar -Delastic.apm.service_name=$POBS_SERVICE_NAME -Delastic.apm.application_packages=$POBS_APPLICATION_PACKAGES -Delastic.apm.log_ecs_reformatting=OVERRIDE -Delastic.apm.server_url=$POBS_APM_SERVER"
ENV JAVA_OPTS "$JAVA_OPTS -noverify"
"""
    return scripts

def entrypoint():
    return 'ENTRYPOINT ["/init"]'

def install_syscall_monitor(package_manager):
    scripts = {
        "apt": """
# System call monitoring
RUN apt-get update && apt-get install -y procps strace

""",
        "yum": """
# System call monitoring
RUN yum install -y sysvinit-tools strace

""",
        "apk": """
# System call monitoring
RUN apk update && apk add procps strace
ADD http://dl-cdn.alpinelinux.org/alpine/v3.15/main/x86_64/libelf-0.185-r0.apk /tmp/
ADD http://dl-cdn.alpinelinux.org/alpine/v3.15/main/x86_64/strace-5.14-r0.apk /tmp/
RUN apk add --allow-untrusted /tmp/libelf-0.185-r0.apk /tmp/strace-5.14-r0.apk

"""
    }
    if package_manager not in scripts:
        return ""
    else:
        return scripts[package_manager]