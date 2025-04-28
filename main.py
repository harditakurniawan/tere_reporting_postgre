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
    
def generate_date_range(inputDate: str) -> dict[str, datetime] :
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
    return dt_obj.strftime('%d/%m/%Y %H:%M')

def validation_keyword_point_value_rule(total_redeem: int, poin_value: str, poin_redeemed: str, total_point=None):
    result = 0

    if total_point is not None:
        result = total_point
    elif not is_null(total_redeem):
        result = total_redeem

    if poin_value == 'Fixed':
        result = poin_redeemed

    elif poin_value == 'Flexible':
        if result <= 0:
            result = poin_redeemed

    elif poin_value == 'Fixed Multiple':
        if result > 0:
            result = poin_redeemed

    else:
        return 0

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
            SELECT
                trx_master.transaction_id,
                trx_master.transaction_date,
                trx_master.status AS status,
                trx_master.origin AS origin,
                trx_master.keyword AS keyword,
                trx_master.keyword AS keyword_title,
                trx_master.msisdn AS msisdn,
                trx_master.channel_id AS channel_code,
                trx_master.poin AS poin,

                COALESCE(tmd.program_name, '') AS program_name,
                COALESCE(tmd.program_experience, '') AS program_experience,
                COALESCE(tmd.poin_value, '') AS poin_value,
                COALESCE(tmd.poin_redeemed, 0) AS poin_redeemed,
                COALESCE(tmd.customer_value, NULL) AS cust_value,
                COALESCE(tmd.start_period, NULL) AS start_date,
                COALESCE(tmd.end_period, NULL) AS end_date,
                COALESCE(tmd.merchant, '') AS merchant,
                COALESCE(tmd.program_bersubsidi, NULL) AS subsidy,
                COALESCE(tmd.channel_id, '') AS sms,
                COALESCE(tmd.channel_id, '') AS umb,
                COALESCE(tmd.total_redeem, NULL) AS total_redeem,
                COALESCE(tmd.brand, '') AS subscriber_brand,
                COALESCE(tmd.region, '') AS subscriber_region,
                COALESCE(tmd.city, '') AS subscriber_branch,
                COALESCE(tmd.tier_name, '') AS subscriber_tier,
                COALESCE(tmd.voucher_code, '') AS voucher_code,

                COALESCE(acc.user_name, '') AS created_by,
                COALESCE(lov1.set_value, '') AS program_owner,
                COALESCE(lov2.set_value, '') AS lifestyle,
                COALESCE(lov2.set_value, '') AS category,
                COALESCE(loc.name, '') AS detail_program_owner,
                COALESCE(loc_prefix.area, '') AS program_regional,
                COALESCE(merchant.merchant_name, '') AS merchant_name,
                SUBSTRING(trx_master.msisdn FROM 3 FOR 6) AS msisdn_prefix
            FROM (
                SELECT *
                FROM mongo.transaction_master
                WHERE transaction_date >= %s
                AND transaction_date < %s
                AND status = 'Success'
                AND origin ~ '^redeem'
        """

        params = [start_date, end_date]

        if exclude_keywords:
            placeholders = ', '.join(['%s'] * len(exclude_keywords))
            raw_query += f" AND keyword NOT IN ({placeholders})"
            params.extend(exclude_keywords)

        raw_query += """
            ) AS trx_master
            LEFT JOIN mongo.transaction_master_detail tmd ON tmd.master_id = trx_master.transaction_id
            LEFT JOIN mongo.accounts acc ON trx_master.created_by = acc._id
            LEFT JOIN mongo.lovs lov1 ON tmd.program_owner = lov1._id
            LEFT JOIN mongo.lovs lov2 ON tmd.program_experience = lov2._id
            LEFT JOIN mongo.merchantv2 merchant ON tmd.merchant = merchant._id
            LEFT JOIN mongo.locations loc ON tmd.program_owner_detail = loc._id
            LEFT JOIN mongo.locationprefixes loc_prefix ON SUBSTRING(trx_master.msisdn FROM 3 FOR 6) = loc_prefix.prefix;
        """

        cursor = connection.cursor(name='fact_detail_cursor')
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
                        transaction_date = ""
                        if line[fields.index("transaction_date")]:
                            transaction_date_unformatted = convert_datetime(f"{line[fields.index("transaction_date")]}".replace(" ", "T").split(".")[0])
                            transaction_date = f"{formatted_trx_date(transaction_date_unformatted)}" or ""

                        start_date = ""
                        if not is_null(line[fields.index("start_date")]):
                            start_date_unformatted = convert_datetime(f"{line[fields.index("start_date")]}".replace(" ", "T").split(".")[0])
                            start_date = f"{formatted_trx_date(start_date_unformatted)}" or ""

                        end_date = ""
                        if not is_null(line[fields.index("end_date")]):
                            end_date_unformatted = convert_datetime(f"{line[fields.index("end_date")]}".replace(" ", "T").split(".")[0])
                            end_date = f"{formatted_trx_date(end_date_unformatted)}" or ""

                        allowed_IH = f"{allowed_indihome_number(line[fields.index("msisdn")])}".lower()
                        
                        poin_redeemed = line[fields.index('poin_redeemed')]
                        total_redeem = line[fields.index('total_redeem')]
                        poin_value = line[fields.index('poin_value')]

                        to_write = (
                            f"{transaction_date}|"
                            f"{line[fields.index('msisdn')]}|"
                            f"{line[fields.index('keyword')]}|"
                            f"{line[fields.index('program_name')]}|"
                            f"{line[fields.index('program_owner')]}|"
                            f"{line[fields.index('detail_program_owner')]}|"
                            f"{line[fields.index('created_by')]}|"
                            f"{line[fields.index('lifestyle')]}|"
                            f"{line[fields.index('category')]}|"
                            f"{line[fields.index('keyword_title')]}|"
                            f"{line[fields.index('sms')]}|"
                            f"{line[fields.index('umb')]}|"
                            f"{ validation_keyword_point_value_rule(total_redeem, poin_value, poin_redeemed) }|"
                            f"{line[fields.index('subscriber_brand') or '']}|"
                            f"{line[fields.index('program_regional')]}|"
                            f"{line[fields.index('cust_value')]}|"
                            f"{start_date}|"
                            f"{end_date}|"
                            f"{line[fields.index('merchant_name')]}|"
                            f"{line[fields.index('subscriber_region')]}|"
                            f"{line[fields.index('subscriber_branch')]}|"
                            f"{line[fields.index('channel_code')]}|"
                            f"{line[fields.index('subsidy')]}|"
                            f"{line[fields.index('subscriber_tier')]}|"
                            f"{line[fields.index('voucher_code')]}|"
                            f"{allowed_IH}"
                        )

                        txt_file.write(to_write + "\n")
                        txt_file.flush()

            dbconnection.close()

            write_ctl_file(filename, single_filename)

        except Exception as e:
            Logger("error", f"ERROR - FactDetailService error: {e} \n")
            Logger("error", f"{traceback.format_exc()}")

    except ValueError as e:
        Logger("error", f"ERROR - Application error: {e} \n")
        Logger("error", f"{traceback.format_exc()}")
    except Exception as e:
        Logger("error", f"ERROR - Unexpected error: {e} \n")
        Logger("error", f"{traceback.format_exc()}")

if __name__ == '__main__':
    main()
