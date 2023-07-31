package ca.uhn.fhir.jpa.starter.custom;

import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;

public class ProprietaryFlatFileStorage {

	public static String storeOnDisk(byte[] base64DecodedBytes) throws IOException {

		OutputStream stream = new FileOutputStream("./create-data/test.tar.gz");
		stream.write(base64DecodedBytes);
		stream.close();
		return null;
	}

}
