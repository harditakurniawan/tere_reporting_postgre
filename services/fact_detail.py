from config.app_config import AppConfig
import pandas as pd

class FactDetailService:
    def __init__(self, logger=None, connection=None):
        self.logger = logger
        self.connection = connection
        
    def getRecords(self, start_date: str, end_date: str, batch_size: int):
        rawQuery = """
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
            ) AS trx_master
            LEFT JOIN mongo.transaction_master_detail tmd ON tmd.master_id = trx_master.transaction_id
            LEFT JOIN mongo.accounts acc ON trx_master.created_by = acc._id
            LEFT JOIN mongo.lovs lov1 ON tmd.program_owner = lov1._id
            LEFT JOIN mongo.lovs lov2 ON tmd.program_experience = lov2._id
            LEFT JOIN mongo.merchantv2 merchant ON tmd.merchant = merchant._id
            LEFT JOIN mongo.locations loc ON tmd.program_owner_detail = loc._id
            LEFT JOIN mongo.locationprefixes loc_prefix ON SUBSTRING(trx_master.msisdn FROM 3 FOR 6) = loc_prefix.prefix;
        """;
        
        params = (start_date, end_date)
        cursor = self.connection.cursor(name='fact_detail_cursor')
        cursor.itersize = batch_size
        cursor.execute(rawQuery, params)
        

        while True:
            batch = cursor.fetchmany(batch_size)
            if not batch:
                self.logger.info("No more data to fetch.")
                break
            self.logger.info(f"Fetched batch with {len(batch)} records.")
            yield pd.DataFrame(batch, columns=[desc[0] for desc in cursor.description])

        cursor.close()