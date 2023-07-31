import psycopg2
import uuid

try:
    print(f"'{str(uuid.uuid4())}'")
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        database="prop",
        user="postgres",
        password="postgres"
    )
    cur = conn.cursor()
    conn.set_session(autocommit=True)
    sql = """INSERT INTO data(id, path_to_file, converted) VALUES(%s::UUID, %s, %s)"""
    # cur.execute(sql, (f"{str(uuid.uuid4())}", "/test/path/file/1.tar.gz", False))
    
    cur.execute("SELECT * FROM data")
    print(cur.fetchall())

    conn.close()
except Exception as e:
    print(e)