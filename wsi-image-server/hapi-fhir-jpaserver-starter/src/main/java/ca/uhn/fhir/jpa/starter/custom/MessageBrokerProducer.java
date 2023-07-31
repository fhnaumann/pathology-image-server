package ca.uhn.fhir.jpa.starter.custom;

import com.rabbitmq.client.Channel;
import com.rabbitmq.client.Connection;
import com.rabbitmq.client.ConnectionFactory;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeoutException;

public class MessageBrokerProducer {
    
    public static void send(String id) {
		 /*
		 ConnectionFactory factory = new ConnectionFactory();
		 factory.setHost("rabbitmq");
		 try(Connection connection = factory.newConnection()) {
			 Channel channel = connection.createChannel();
			 channel.queueDeclare("hello", false, false, false, null);
			 String message = "abc";
			 channel.basicPublish("", "hello", null, message.getBytes(StandardCharsets.UTF_8));
			 System.out.println(" [x] Sent '" + message + "'");
		 } catch (IOException | TimeoutException e) {
			 e.printStackTrace();
		 }*/
	 }
}
