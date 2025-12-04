from datetime import datetime, timedelta
from psycopg2 import OperationalError
from dateutil import parser
from typing import List, Any
import pandas as pd
import configparser
import traceback
import psycopg2
import os


# ==============================================
#                   UTILS
# ==============================================
def Logger(level, message):
    currentTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print("{} - {} - {}".format(currentTime, level.upper(), message))


def allowed_msisdn(msisdn):
    prefixes = ("08", "62", "81", "82", "83", "85", "628")
    return any(msisdn.startswith(prefix) and msisdn[len(prefix):].isdigit() for prefix in prefixes)


def allowed_indihome_number(msisdn):
    return not allowed_msisdn(msisdn)


def is_null(value):
    return pd.isna(value) or str(value).strip().lower() in ('', 'null', 'none', 'nat')


def safe_get_field(line, fields, field_name, default=''):
    try:
        if field_name in fields:
            value = line[fields.index(field_name)]
            if not is_null(value):
                return value
    except Exception:
        pass
    return default


def initialize_db_connection(dbname, dbuser, dbpassword, dbhost, dbport):
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
        Logger("error", "ERROR - DB Connection error: {} \n".format(e))
        Logger("error", "Database connection failed: {}".format(e))
        raise


def generate_date_range(inputDate):
    date_obj = pd.to_datetime(inputDate)
    last_day = date_obj - pd.Timedelta(days=1)

    parse_from = parser.isoparse(
        '{}T17:00:00.000Z'.format(last_day.strftime("%Y-%m-%d"))
    )
    parse_to = parser.isoparse(
        '{}T17:00:00.000Z'.format(inputDate)
    )

    Logger("info", "Generated date range: start_date {} | end_date {}".format(parse_from, parse_to))
    return {"start_date": parse_from, "end_date": parse_to}


def convert_datetime(dt_str):
    return parser.isoparse(dt_str).astimezone()


def formatted_trx_date(dt_str):
    dt_obj = pd.to_datetime(str(dt_str).split("+")[0], format='%Y-%m-%d %H:%M:%S')
    dt_obj += pd.Timedelta(hours=7)
    return dt_obj.strftime('%Y%m%d%H%M%S')


def format_msisdn(msisdn):
    if allowed_indihome_number(msisdn):
        return msisdn
    return "62{}".format(msisdn) if msisdn.startswith('8') else msisdn


def write_ctl_file(filename, single_filename):
    with open(filename, "rb") as f:
        rowCount = sum(1 for _ in f)

    fileSize = os.path.getsize(filename)
    ctlName = filename.replace(".dat", ".ctl")

    with open(ctlName, "w") as ctl_file:
        ctl_file.write('{}|{}|{}'.format(single_filename, rowCount, fileSize))


# ==============================================
#                   SERVICE
# ==============================================
def get_records(connection, start_date, end_date, exclude_keywords, batch_size):
    raw_query = """
        SELECT *
        FROM mongo.report_redeem_transaction
        WHERE transaction_date >= %s
        AND transaction_date < %s
    """

    params = [start_date, end_date]

    if exclude_keywords:
        placeholders = ', '.join(['%s'] * len(exclude_keywords))
        raw_query += " AND keyword NOT IN ({})".format(placeholders)
        params.extend(exclude_keywords)

    cursor = connection.cursor(name='fact_atp_redeem_cursor')
    cursor.itersize = batch_size
    cursor.execute(raw_query, params)

    while True:
        batch = cursor.fetchmany(batch_size)
        if not batch:
            Logger("info", "No more data to fetch.")
            break

        Logger("info", "Fetched batch with {} records.".format(len(batch)))
        yield pd.DataFrame(batch, columns=[desc[0] for desc in cursor.description])

    cursor.close()


def main():
    try:
        # ====================== SETUP CONFIG ====================== #
        config = configparser.ConfigParser()
        config.read('.env')

        BATCH_SIZE = int(config.get('APP', 'BATCH_SIZE', fallback='10000'))
        DEFAULT_PERIOD = int(config.get('APP', 'DEFAULT_PERIOD', fallback='3'))
        TARGET_DIR = config.get('APP', 'TARGET_DIR', fallback='./report')
        DB_HOST = config.get('DB', 'DB_HOST', fallback='127.0.0.1')
        DB_PORT = config.get('DB', 'DB_PORT', fallback='5432')
        DB_NAME = config.get('DB', 'DB_NAME', fallback='slreport_db')
        DB_USERNAME = config.get('DB', 'DB_USERNAME', fallback='')
        DB_PASSWORD = config.get('DB', 'DB_PASSWORD', fallback='')

        # ====================== INPUT FROM CLI ====================== #
        parse_date = str(input("Target date (required | format: YYYY-MM-DD) : ")).strip()
        filename = str(input("File name (required | ex: filename.dat) : ")).strip()
        exclude_input = str(input("Exclude keyword (optional | seperated with comma if more than one): ")).strip()

        # ====================== DB CONNECTION ====================== #
        dbconnection = initialize_db_connection(DB_NAME, DB_USERNAME, DB_PASSWORD, DB_HOST, DB_PORT)

        # ====================== MAIN TASK ====================== #
        exclude_keywords = [e.strip().upper() for e in exclude_input.split(',')] if exclude_input else []

        date_range = generate_date_range(parse_date)
        start_date = date_range['start_date']
        end_date = date_range['end_date']

        single_filename = filename
        filename = "{}/{}".format(TARGET_DIR, filename)

        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            with open(filename, "a") as txt_file:
                for batches in get_records(dbconnection, start_date, end_date, exclude_keywords, BATCH_SIZE):

                    fields = batches.columns.tolist()
                    batch_numpy = batches.to_numpy()

                    for line in batch_numpy:
                        execution_date = ""

                        if line[fields.index("execution_date")]:
                            raw = "{}".format(line[fields.index("execution_date")])
                            raw = raw.replace(" ", "T").split(".")[0]
                            execution_date_unformatted = convert_datetime(raw)
                            execution_date = formatted_trx_date(execution_date_unformatted)

                        allowed_IH = str(allowed_indihome_number(line[fields.index('msisdn')])).lower()
                        msisdn_formatted = format_msisdn(line[fields.index("msisdn")])

                        values = [
                            safe_get_field(line, fields, 'transaction_id'),
                            safe_get_field(line, fields, 'keyword'),
                            safe_get_field(line, fields, 'keyword_title'),
                            safe_get_field(line, fields, 'execution_type'),
                            safe_get_field(line, fields, 'product_id'),
                            safe_get_field(line, fields, 'period1'),
                            safe_get_field(line, fields, 'period2'),
                            safe_get_field(line, fields, 'subscriber_id'),
                            msisdn_formatted,
                            safe_get_field(line, fields, 'return_value'),
                            execution_date,
                            safe_get_field(line, fields, 'channel_code'),
                            safe_get_field(line, fields, 'transaction_status'),
                            safe_get_field(line, fields, 'trdm_last_act'),
                            safe_get_field(line, fields, 'trdm_act_status'),
                            safe_get_field(line, fields, 'trdm_evd_id'),
                            safe_get_field(line, fields, 'trdm_flag_kirim'),
                            safe_get_field(line, fields, 'trdm_geneva_exec'),
                            safe_get_field(line, fields, 'trdm_keyword'),
                            safe_get_field(line, fields, 'trdm_tgl_kirim'),
                            safe_get_field(line, fields, 'channel_transaction_id'),
                            safe_get_field(line, fields, 'card_type'),
                            safe_get_field(line, fields, 'brand'),
                            safe_get_field(line, fields, 'subscriber_region'),
                            safe_get_field(line, fields, 'subscriber_branch'),
                            safe_get_field(line, fields, 'lacci'),
                            allowed_IH
                        ]

                        txt_file.write("|".join(str(v) for v in values) + "\n")
                        txt_file.flush()

            dbconnection.close()
            write_ctl_file(filename, single_filename)

        except Exception as e:
            Logger("error", "ERROR - FactAtpRedeemService error: {} \n".format(e))
            Logger("error", traceback.format_exc())

    except Exception as e:
        Logger("error", "ERROR - Unexpected error: {} \n".format(e))
        Logger("error", traceback.format_exc())


if __name__ == '__main__':
    main()
