package ca.uhn.fhir.jpa.starter.custom;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;

public class ProprietaryDB {

	private final String url;
	private final String user;
	private final String password;

	public ProprietaryDB(String dbHost, String dbName, String user, String password) {
		this.url = String.format("jdbc:postgresql://%s/%s", dbHost, dbName);
		this.user = user;
		this.password = password;
	}

	public void insertProprietaryFile() {
		try(Connection connection = DriverManager.getConnection(url, user, password)) {
			String insert = "INSERT INTO files (path, datatype, finished_converting) VALUES (?, ?, ?);";
			PreparedStatement preparedStatement = connection.prepareStatement(insert);


			preparedStatement.executeUpdate();
		} catch (SQLException e) {
			e.printStackTrace();
		}
	}
}
