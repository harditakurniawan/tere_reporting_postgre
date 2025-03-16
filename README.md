# Reporting Fact Detail (PostgreSQL)

## Structure Folder
root/
├── config/
│   └── app_config.py
├── database/
│   └── postgres.py
├── model/
│   └── model.txt
├── services/
│   └── fact_detail.py
├── utils/
│   ├── datetime_utils.py
│   ├── logger.py
│   └── utils.py
├── main.py
└── .env

## How to run:
* Adjust env
* Install depedency
* Create db and its tables (see schema in model.txt)
* Activate virtual env (optional) and run python3 main.py
* Input target date with format YYYY-MM-DD
* Input file name (ex: fact_detail.dat)