from datetime import datetime, timedelta
from psycopg2 import OperationalError
from dateutil import parser
import pandas as pd
import configparser
import traceback
import psycopg2
import os


# ==============================================
#                   UTILS
# ==============================================
def Logger(level: str, message: str) -> None :
    currentTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f"{currentTime} - {level.upper()} - {message}")

def allowed_msisdn(msisdn: str) -> str :
    prefixes = ("08", "62", "81", "82", "83", "85", "628")
    return any(msisdn.startswith(prefix) and msisdn[len(prefix):].isdigit() for prefix in prefixes)

def allowed_indihome_number(msisdn: str) -> bool :
        return allowed_msisdn(msisdn) is False

def is_null(value: any) -> bool :
    return pd.isna(value) or str(value).strip().lower() in ('', 'null', 'none', 'nat')

def safe_get_field(line, fields, field_name, default=''):
    return line[fields.index(field_name)] if field_name in fields and not is_null(line[fields.index(field_name)]) else default

def initialize_db_connection(dbname: str, dbuser: str, dbpassword: str, dbhost: str, dbport: str) :
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=dbuser,
            password=dbpassword,
            host=dbhost,
            port=dbport
        )

        Logger("info", "Connected to the database successfully \n")
        return conn
    except OperationalError as e:
        Logger("error", f"ERROR - DB Connection error: {e} \n")
        Logger("error", f"Database connection failed: {e}")
        raise Exception(e)
    
def generate_date_range(inputDate: str) :
    date_obj = pd.to_datetime(inputDate)
    last_day = date_obj - pd.Timedelta(days=1)
    parse_from = parser.isoparse(f'{last_day.strftime("%Y-%m-%d")}T17:00:00.000Z')
    parse_to = parser.isoparse(f'{inputDate}T17:00:00.000Z')

    Logger("info", f"Generated date range: start_date {parse_from} | end_date {parse_to}")

    return { "start_date": parse_from, "end_date": parse_to }
    
def convert_datetime(dt_str: str) -> datetime :
    return parser.isoparse(dt_str).astimezone()

def formatted_trx_date(dt_str: str) -> str :
    dt_obj = pd.to_datetime(str(dt_str).split("+")[0], format='%Y-%m-%d %H:%M:%S')
    dt_obj += pd.Timedelta(hours=7)
    return dt_obj.strftime('%Y%m%d%H%M%S')

def format_msisdn(msisdn: str) -> str :
    if allowed_indihome_number(msisdn):
        return msisdn
    else:
        return f"62{msisdn}" if msisdn.startswith('8') else msisdn

def write_ctl_file(filename: str, single_filename: str):
    with open(filename, "rb") as f:
        rowCount = sum(1 for _ in f)

    fileSize = os.path.getsize(filename)
    ctlName = filename.replace(".dat", ".ctl")
    with open(ctlName, "w") as ctl_file:
        ctl_file.write(f'{single_filename}|{rowCount}|{fileSize}')

# ==============================================
#                   SERVICE
# ==============================================
def get_records(connection, start_date: str, end_date: str, exclude_keywords: list[str], batch_size: int) :
    raw_query = """
        SELECT *
        FROM mongo.report_redeem_transaction
        WHERE transaction_date >= %s
        AND transaction_date < %s
    """

    params = [start_date, end_date]

    if exclude_keywords:
        placeholders = ', '.join(['%s'] * len(exclude_keywords))
        raw_query += f" AND keyword NOT IN ({placeholders})"
        params.extend(exclude_keywords)

    cursor = connection.cursor(name='fact_atp_redeem_cursor')
    cursor.itersize = batch_size
    cursor.execute(raw_query, params)
    
    while True:
        batch = cursor.fetchmany(batch_size)
        if not batch:
            Logger("info", "No more data to fetch.")
            break
        Logger("info", f"Fetched batch with {len(batch)} records.")
        yield pd.DataFrame(batch, columns=[desc[0] for desc in cursor.description])

    cursor.close()

def main():
    try:
        # ====================== SETUP CONFIG ====================== #
        config = configparser.ConfigParser()
        config.read('.env')
        BATCH_SIZE = int(config.get('APP', 'BATCH_SIZE', fallback=10000))
        DEFAULT_PERIOD = int(config.get('APP', 'DEFAULT_PERIOD', fallback=3))
        TARGET_DIR = config.get('APP', 'TARGET_DIR', fallback='./report')
        DB_HOST = config.get('DB', 'DB_HOST', fallback='127.0.0.1')
        DB_PORT = config.get('DB', 'DB_PORT', fallback='5432')
        DB_NAME = config.get('DB', 'DB_NAME', fallback='slreport_db')
        DB_USERNAME = config.get('DB', 'DB_USERNAME', fallback='')
        DB_PASSWORD = config.get('DB', 'DB_PASSWORD', fallback='')


        # ====================== INPUT FROM CLI ====================== #
        parse_date = str(input("Target date (required | format: YYYY-MM-DD) : ")).strip()
        filename = str(input("File name (required | ex: filename.dat) : ")).strip()
        exclude_input = str(input("Exclude keyword (optional | seperater with coma if more than one): ")).strip()


        # ====================== DB CONNECTION ====================== #
        dbconnection = initialize_db_connection(DB_NAME, DB_USERNAME, DB_PASSWORD, DB_HOST, DB_PORT)


        # ====================== MAIN TASK ====================== #
        exclude_keywords = [exclude.strip().upper() for exclude in exclude_input.split(',')] if exclude_input else []
        date_range = generate_date_range(parse_date)
        start_date = date_range.get('start_date')
        end_date = date_range.get('end_date')
        single_filename = filename
        filename = f"{TARGET_DIR}/{filename}"
        
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "a") as txt_file:
                for batches in get_records(dbconnection, start_date, end_date, exclude_keywords, BATCH_SIZE):

                    fields = batches.columns.tolist()
                    batch_numpy = batches.to_numpy()
                    
                    for line in batch_numpy:
                        execution_date = ""
                        if line[fields.index("execution_date")]:
                            execution_date_unformatted = convert_datetime(f"{line[fields.index('execution_date')]}".replace(" ", "T").split(".")[0])
                            execution_date = f"{formatted_trx_date(execution_date_unformatted)}" or ""

                        allowed_IH = f"{allowed_indihome_number(line[fields.index('msisdn')])}".lower()
                        msisdn_formatted = format_msisdn(line[fields.index("msisdn")])

                        to_write = (
                            f"{safe_get_field(line, fields, 'transaction_id')}|"
                            f"{safe_get_field(line, fields, 'keyword')}|"
                            f"{safe_get_field(line, fields, 'keyword_title')}|"
                            f"{safe_get_field(line, fields, 'execution_type')}|"
                            f"{safe_get_field(line, fields, 'product_id')}|"
                            f"{safe_get_field(line, fields, 'period1')}|"
                            f"{safe_get_field(line, fields, 'period2')}|"
                            f"{safe_get_field(line, fields, 'subscriber_id')}|"
                            f"{msisdn_formatted}|"
                            f"{safe_get_field(line, fields, 'return_value')}|"
                            f"{execution_date}|"
                            f"{safe_get_field(line, fields, 'channel_code')}|"
                            f"{safe_get_field(line, fields, 'transaction_status')}|"
                            f"{safe_get_field(line, fields, 'trdm_last_act')}|"
                            f"{safe_get_field(line, fields, 'trdm_act_status')}|"
                            f"{safe_get_field(line, fields, 'trdm_evd_id')}|"
                            f"{safe_get_field(line, fields, 'trdm_flag_kirim')}|"
                            f"{safe_get_field(line, fields, 'trdm_geneva_exec')}|"
                            f"{safe_get_field(line, fields, 'trdm_keyword')}|"
                            f"{safe_get_field(line, fields, 'trdm_tgl_kirim')}|"
                            f"{safe_get_field(line, fields, 'channel_transaction_id')}|"
                            f"{safe_get_field(line, fields, 'card_type')}|"
                            f"{safe_get_field(line, fields, 'brand')}|"
                            f"{safe_get_field(line, fields, 'subscriber_region')}|"
                            f"{safe_get_field(line, fields, 'subscriber_branch')}|"
                            f"{safe_get_field(line, fields, 'lacci')}|"
                            f"{allowed_IH}"
                        )

                        txt_file.write(to_write + "\n")
                        txt_file.flush()

            dbconnection.close()

            write_ctl_file(filename, single_filename)

        except Exception as e:
            Logger("error", f"ERROR - FactAtpRedeemService error: {e} \n")
            Logger("error", f"{traceback.format_exc()}")

    except ValueError as e:
        Logger("error", f"ERROR - Application error: {e} \n")
        Logger("error", f"{traceback.format_exc()}")
    except Exception as e:
        Logger("error", f"ERROR - Unexpected error: {e} \n")
        Logger("error", f"{traceback.format_exc()}")

if __name__ == '__main__':
    main()
