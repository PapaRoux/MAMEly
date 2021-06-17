import sqlite3
from sqlite3 import Error


def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by the db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)

    return conn
    
def create_table(conn, create_table_sql):
    """ create a table from the create_table_sql statement
    :param conn: Connection object
    :param create_table_sql: a CREATE TABLE statement
    :return:
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e)    
    
    
    
    
def create_rom(conn, rom):
    """
    Create a new rom
    :param conn:
    :param rom:
    :return:
    """

    sql = ''' INSERT INTO roms(romname, description, genre, rating, favorite, ignore)
              VALUES(?,?,?,?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, rom)
    conn.commit()

    return cur.lastrowid


def select_all_roms(conn):
    """
    Query all rows in the roms table
    :param conn: the Connection object
    :return:
    """
    cur = conn.cursor()
    cur.execute("SELECT * FROM roms")

    rows = cur.fetchall()

    for row in rows:
        print(row)

    
    
    
    
def main():
    database = r"pythonsqlite.db"

    # create a database connection
    conn = create_connection(database)
    
    sql_create_roms_table = """CREATE TABLE IF NOT EXISTS roms (
                                    romname text PRIMARY KEY,
                                    description text NOT NULL,
                                    genre text,
                                    rating text,
                                    favorite integer,
                                    ignore integer
                                );"""    
    
        # create tables
    if conn is not None:

        # create roms table
        create_table(conn, sql_create_roms_table)
    else:
        print("Error! cannot create the database connection.")
    
    
    with conn:

        rom_1 = ('pacman', 'Pac Man', 'Maze', '', 1, 0)
        rom_2 = ('mspacman', 'Ms. Pac Man', 'Maze', '', 1, 0)

        # create roms
        create_rom(conn, rom_1)
        create_rom(conn, rom_2)    
    
    
    
    with conn:
        select_all_roms(conn)
        
    


if __name__ == '__main__':
    main()