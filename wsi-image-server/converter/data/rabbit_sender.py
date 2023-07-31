import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rabbitmq'))
channel = connection.channel()

channel.queue_declare(queue='hello')

json_body = \
    """
    {
        "uuid": "70e158e3-50e4-40ff-880b-3b95a532c195",
        "path": "some/test/path/file.tar.gz",
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
    """

# channel.basic_publish(exchange='', routing_key='hello', body=json_body)
print(" [x] Sent 'Hello World!'")
# connection.close()