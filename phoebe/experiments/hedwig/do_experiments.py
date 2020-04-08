#!/usr/bin/python
# -*- coding: utf-8 -*-
# Filename: do_experiments.py

import os, datetime, time, json, re, argparse, subprocess, signal, random, socket
from difflib import Differ
import smtplib, imaplib, email
from email.header import Header
from email.header import decode_header
from email.utils import parseaddr, formataddr

import logging

SMTP_SERVER = "localhost"
SMTP_SERVER_PORT = 30025
IMAP_SERVER = "localhost"
IMAP_SERVER_PORT = 30143

SENDER = {"name": "longz", "address": "longz@localhost", "password": "123456"}
RECEIVER = {"name": "test", "address": "test@localhost", "password": "654321"}

INJECTOR = None
HEDWIG_RESET = "JAVA_HOME=/home/gluckzhang/.sdkman/candidates/java/current /home/gluckzhang/development/hedwig-0.7/hedwig-0.7-binary/bin/run.sh restart"

def handle_sigint(sig, frame):
    global INJECTOR
    if (INJECTOR != None): os.killpg(os.getpgid(INJECTOR.pid), signal.SIGTERM)
    exit()

def handle_args():
    parser = argparse.ArgumentParser(
        description="Conduct fault injection experiments on HedWig server")
    parser.add_argument("-p", "--pid", type=int, help="the pid of HedWig")
    parser.add_argument("-c", "--config", help="the fault injection config (.json)")
    parser.add_argument("-i", "--injector", help="the path to syscall_injector.py")
    parser.add_argument("-d", "--dataset", help="the folder that contains .msg files")
    return parser.parse_args()

def check_hedwig():
    pattern = re.compile(r'(\d+)\s+com\.hs\.mail\.container\.simple\.SimpleSpringContainer')

    jps_output = subprocess.check_output("jps -l", shell=True)
    pids = pattern.findall(jps_output)
    if len(pids) == 1:
        result = {"status": "running", "pid": pids[0]}
    else:
        logging.warning("hedwig is down, needs to be restarted")
        os.system(HEDWIG_RESET)
        time.sleep(3)
        jps_output = subprocess.check_output("jps -l", shell=True)
        pids = pattern.findall(jps_output)
        if len(pids) == 1:
            result = {"status": "restarted", "pid": pids[0]}
        else:
            result = {"status": "down", "pid": 0}
            logging.warning("hedwig is down, failed to be restarted!")
    return result


def randomly_pickup(dataset):
    email_path = random.choice(dataset)
    with open(email_path) as file:
        original_email = email.message_from_file(file)
    return original_email

def do_experiment(experiment, pid, injector_path, dataset):
    global SENDER
    global RECEIVER
    global INJECTOR

    # experiment principle
    # while loop for the duration of the experiment:
    #   start the syscall_injector
    #   randomly pickup an email from the dataset
    #   send email -> fetch email -> validate email
    #   stop the syscall_injector
    #   restart hedwig if necessary
    logging.info("begin the following experiment")
    logging.info(experiment)
    end_at = time.time() + experiment["experiment_duration"]
    sleep_time_after_sending = 30
    hedwig_pid = pid

    # start the injector
    INJECTOR = subprocess.Popen("%s -p %s -P %s --errorno=%s %s"%(
        injector_path, hedwig_pid, experiment["failure_rate"], experiment["error_code"], experiment["syscall_name"]
    ), close_fds=True, shell=True, preexec_fn=os.setsid)

    result = {"rounds": 0, "succeeded": 0, "sending_failures": 0, "fetching_failures": 0, "validation_failures": 0, "server_crashed": 0}
    while True:
        if time.time() > end_at: break
        # logging.info(INJECTOR.stdout.readline())
        #   randomly pickup an email from the dataset
        original_email = randomly_pickup(dataset)
        #   send email -> fetch email -> validate email
        try:
            send_email(SENDER, RECEIVER, original_email)
            logging.info("send an email to the receiver")
        except:
            logging.info("failed to send!")
            result["rounds"] = result["rounds"] + 1
            time.sleep(3)
            hedwig_status = check_hedwig()
            if hedwig_status["status"] == "restarted":
                result["server_crashed"] = result["server_crashed"] + 1
                hedwig_pid = hedwig_status["pid"]
                break
            elif hedwig_status["status"] == "running":
                result["sending_failures"] = result["sending_failures"] + 1
                continue
            else:
                # failed to restart hedwig, should stop the experiments
                logging.error("failed to restart hedwig, experiments should be stopped")
                result["fatal"] = True
                break

        # logging.info(INJECTOR.stdout.readline())
        time.sleep(sleep_time_after_sending) # wait, the server needs some time to handle the mails

        # logging.info(INJECTOR.stdout.readline())
        try:
            fetched_email = fetch_email(RECEIVER)
            logging.info("fetch the email from the receiver")
        except:
            logging.info("failed to fetch!")
            result["rounds"] = result["rounds"] + 1
            time.sleep(3)
            hedwig_status = check_hedwig()
            if hedwig_status["status"] == "restarted":
                result["server_crashed"] = result["server_crashed"] + 1
                hedwig_pid = hedwig_status["pid"]
                break
            elif hedwig_status["status"] == "running":
                result["fetching_failures"] = result["fetching_failures"] + 1
                continue
            else:
                # failed to restart hedwig, should stop the experiments
                logging.error("failed to restart hedwig, experiments should be stopped")
                result["fatal"] = True
                break

        result["rounds"] = result["rounds"] + 1
        if validate_email(original_email, fetched_email):
            result["succeeded"] = result["succeeded"] + 1
        else:
            result["validation_failures"] = result["validation_failures"] + 1
        logging.info(result)

    # end the injector
    os.killpg(os.getpgid(INJECTOR.pid), signal.SIGTERM)

    # post inspection: whether abnormal behavior exists even after turning off the injector
    # if so, the server needs to be restarted
    logging.info("post inspection begins")
    original_email = randomly_pickup(dataset)
    try:
        send_email(SENDER, RECEIVER, original_email)
        time.sleep(sleep_time_after_sending)
        fetched_email = fetch_email(RECEIVER)
        if validate_email(original_email, fetched_email):
            result["post_inspection"] = "passed"
        else:
            result["post_inspection"] = "failed"
    except:
        result["post_inspection"] = "failed"
    logging.info(result)

    experiment["result"] = result
    return experiment

def format_addr(email):
    name, addr = parseaddr(email)
    return formataddr((Header(name, 'utf-8').encode(), addr))

def send_email(sender, receiver, message):
    global SMTP_SERVER
    global SMTP_SERVER_PORT

    message['From'] = format_addr('%s <%s>' % (sender["name"], sender["address"]))
    message['To'] = format_addr('%s <%s>' % (receiver["name"], receiver["address"]))

    server = smtplib.SMTP(SMTP_SERVER, SMTP_SERVER_PORT)
    # server.login(sender["address"], sender["password"])
    server.sendmail(sender["address"], [receiver["address"]], message.as_string())
    # server.quit()

def decode_str(string):
    value, charset = decode_header(string)[0]
    if charset:
        value = value.decode(charset)
    return value

def fetch_email(receiver):
    global IMAP_SERVER
    global IMAP_SERVER_PORT

    server = imaplib.IMAP4(IMAP_SERVER, IMAP_SERVER_PORT)
    server.login(receiver["address"],receiver["password"])
    server.select("INBOX")
    typ, data = server.search(None, "ALL")

    index = data[0].split()
    typ, data = server.fetch(index[-1], '(RFC822)')
    try:
        message = email.message_from_string(data[0][1].decode("utf-8"))
    except UnicodeEncodeError:
        logging.warning("failed to decode the email because of UnicodeEncodeError")

    server.close()
    server.logout()

    return message

def extract_basic_info(message):
    subject = ""
    content_str = ""
    try:
        subject = decode_str(message.get("Subject", ""))
        if message.is_multipart():
            messages = message.get_payload()
            for msg in messages:
                content_str = content_str + msg.get_payload(decode = True)
        else:
            content_str = message.get_payload(decode = True)
    except UnicodeEncodeError:
        logging.warning("failed to decode the email because of UnicodeEncodeError")

    return {"subject": subject.replace("\r\n", "\n"), "content": content_str.replace("\r\n", "\n")}

def validate_email(original_email, fetched_email):
    ori = extract_basic_info(original_email)
    fetched = extract_basic_info(fetched_email)
    subject_match = True if ori["subject"] == fetched["subject"] else False
    content_match = True if ori["content"] == fetched["content"] else False
    if not subject_match:
        logging.debug("subject match failed")
        logging.debug(list(Differ().compare(ori["subject"], fetched["subject"])))
    if not content_match:
        logging.debug("content match failed")
    return subject_match and content_match

def save_experiment_result(experiments):
    with open("fi_experiments_result.json", "wt") as output:
        json.dump(experiments, output, indent = 2)

def extract_messages(dataset_path):
    dataset = list()
    for file in os.listdir(dataset_path):
        if os.path.splitext(file)[1] == '.msg':
            dataset.append(os.path.join(dataset_path, file))
    return dataset

def main(args):
    dataset = extract_messages(args.dataset)

    with open(args.config, 'rt') as file:
        experiments = json.load(file)
        for experiment in experiments["experiments"]:
            if "result" in experiment: continue
            experiment = do_experiment(experiment, args.pid, args.injector, dataset)
            save_experiment_result(experiments)
            if "fatal" in experiment["result"] and experiment["result"]["fatal"]: break

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    signal.signal(signal.SIGINT, handle_sigint)

    socket_default_timeout = 5
    socket.setdefaulttimeout(socket_default_timeout)

    args = handle_args()
    main(args)