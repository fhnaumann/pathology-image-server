import pika, sys, os
from threading import Thread
import converter
import filler
from concurrent import futures
import sender
import json
from exceptions import format_exception
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s", datefmt="%d/%b/%Y %H:%M:%S")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq')) # change-me
    channel = connection.channel()

    queue_name = 'hello' # matches queue name in HAPI FHIR interceptor

    channel.queue_declare(queue=queue_name) 
    
    def start_conversion(json_body: str):
        data = json.loads(json_body)
        business_id: str = data["uuid"]
        try:
            conv, kc_info = converter.Converter.fromBroker(data)
            business_id, path_to_dcm_folder = conv.handle()
            sender.send_and_cleanup(business_id, kc_info=kc_info, path_to_dcm_folder=path_to_dcm_folder)
            sender.update_prop_db_status(business_id, converted=True)
        except Exception as e:
            sender.update_prop_db_status(business_id, converted=False, error_msg=format_exception(e))

    def callback(ch, method, properties, body):
        logger.debug(" [x] Received %r", body)
        t = Thread(target=start_conversion, args=[body])
        t.start()

    print(' [*] Awaiting RPC request. To exit press CTRL+C')

    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)