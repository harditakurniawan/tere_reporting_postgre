import pandas as pd
import numpy as np
import os

class Utils:
    def formatted_trx_date(self, dt_str: str):
        dt_obj = pd.to_datetime(str(dt_str).split("+")[0], format='%Y-%m-%d %H:%M:%S')
        dt_obj += pd.Timedelta(hours=7)
        return dt_obj.strftime('%d/%m/%Y %H:%M')
    
    def allowed_msisdn(self, msisdn: str):
        prefixes = ("08", "62", "81", "82", "83", "85", "628");
        return any(msisdn.startswith(prefix) and msisdn[len(prefix):].isdigit() for prefix in prefixes);
    
    def allowed_indihome_number(self, msisdn: str):
        return self.allowed_msisdn(msisdn) is False
    
    def validation_keyword_point_value_rule(self, total_redeem: int, poin_value: str, poin_redeemed: str, total_point=None) -> str:
        result = 0

        if total_point is not None:
            result = total_point
        elif not self.is_null(total_redeem):
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
    
    def write_ctl_file(self, filename: str, single_filename: str):
        with open(filename, "rb") as f:
            rowCount = sum(1 for _ in f)

        fileSize = os.path.getsize(filename)
        ctlName = filename.replace(".dat", ".ctl")
        with open(ctlName, "w") as ctl_file:
            ctl_file.write(f'{single_filename}|{rowCount}|{fileSize}')
            
    def is_null(self, value: any) -> bool :
        return pd.isna(value) or str(value).strip().lower() in ('', 'null', 'none', 'nat')