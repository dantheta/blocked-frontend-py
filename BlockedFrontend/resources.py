import yaml
import csv
from flask import current_app

__all__ = ['load_country_data','load_isp_data','load_data','load_csv']

def load_data(filename):
    with current_app.open_resource('data/'+filename+'.yml', 'r') as fp:
        return yaml.safe_load(fp)

def load_csv(filename):
    with current_app.open_resource('data/'+filename+'.csv', 'r') as fp:
        reader = csv.reader(fp)
        for row in reader:
            yield row

def load_country_data():
    return load_data('countries')

def load_isp_data():
    return load_data('isps')
