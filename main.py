from database.postgres import PostgresDB
from services.fact_detail import FactDetailService
from utils.datetime_utils import DatetimeUtils
from utils.logger import Logger
from utils.utils import Utils
from config.app_config import AppConfig
import traceback
import os

# import sys
# import psutil
# import pandas as pd

def main():
    try:
        config = AppConfig()
        config.reload_config()

        # Input from cli
        parse_date = str(input("Target date (required | format: YYYY-MM-DD) : ")).strip()
        filename = str(input("File name (required | ex: filename.dat) : ")).strip()
        exclude_input = str(input("Exclude keyword (optional | seperater with coma if more than one): ")).strip()

        # DB Connection
        db = PostgresDB(dbname=config.DB_NAME, user=config.DB_USERNAME, password=config.DB_PASSWPRD, host=config.DB_HOST, port=config.DB_PORT)
        connection = db.get_connection()

        # Initialization
        logger = Logger().get_logger()
        utils = Utils()
        datetime_utils = DatetimeUtils(logger=logger)
        fact_detail_service = FactDetailService(logger=logger, connection=connection)

        # Main task
        exclude_keywords = [exclude.strip().upper() for exclude in exclude_input.split(',')] if exclude_input else []
        date_range = datetime_utils.generate_date_range(parse_date);
        start_date = date_range.get('start_date')
        end_date = date_range.get('end_date')
        single_filename = filename
        filename = f"{config.TARGET_DIR}/{filename}"
        
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "a") as txt_file:
                for batches in fact_detail_service.getRecords(start_date, end_date, exclude_keywords, config.BATCH_SIZE):
                    # df = pd.DataFrame.from_records(batches)
                    # mem_usage = sys.getsizeof(df)

                    fields = batches.columns.tolist()
                    batch_numpy = batches.to_numpy()
                    
                    for line in batch_numpy:
                        transaction_date = ""
                        if line[fields.index("transaction_date")]:
                            transaction_date_unformatted = datetime_utils.convert_datetime(f"{line[fields.index("transaction_date")]}".replace(" ", "T").split(".")[0])
                            transaction_date = f"{utils.formatted_trx_date(transaction_date_unformatted)}" or ""

                        start_date = ""
                        if not utils.is_null(line[fields.index("start_date")]):
                            start_date_unformatted = datetime_utils.convert_datetime(f"{line[fields.index("start_date")]}".replace(" ", "T").split(".")[0])
                            start_date = f"{utils.formatted_trx_date(start_date_unformatted)}" or ""

                        end_date = ""
                        if not utils.is_null(line[fields.index("end_date")]):
                            end_date_unformatted = datetime_utils.convert_datetime(f"{line[fields.index("end_date")]}".replace(" ", "T").split(".")[0])
                            end_date = f"{utils.formatted_trx_date(end_date_unformatted)}" or ""

                        allowed_IH = f"{utils.allowed_indihome_number(line[fields.index("msisdn")])}".lower()
                        
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
                            f"{ utils.validation_keyword_point_value_rule(total_redeem, poin_value, poin_redeemed) }|"
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

                    # print("===================== MEM. USAGE ========================")
                    # process = psutil.Process(os.getpid())
                    # mem_usage = process.memory_info().rss / (1024 * 1024)
                    # print(f"Memory usage: {mem_usage:.2f} MB")

            connection.close()

            utils.write_ctl_file(filename, single_filename)

        except Exception as e:
            logger.error(f"FactDetailService error: {e}")
            logger.error(traceback.format_exc()) 

    except ValueError as e:
        logger.error(f"Application error: {e}")
        logger.error(traceback.format_exc()) 
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc()) 

if __name__ == '__main__':
    main()
