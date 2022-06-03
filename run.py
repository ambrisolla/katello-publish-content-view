#!/usr/bin/python3
import os
import requests
from requests.auth import HTTPBasicAuth
import sys
import yaml
import json
from datetime import datetime
import argparse

class Katello:

  def __init__(self, **kwargs):
    env = kwargs['env']
    # set path to script directory
    self.full_path = os.path.abspath(os.path.dirname(__file__))
    # set log file path
    self.log_file = f'{self.full_path}/run.log'
    # load data from config.yml file
    yaml_data = open(f'{self.full_path}/config.yml', 'r').read()
    self.config = yaml.safe_load(yaml_data)['envs'][env]
    #  disable SSL warnings ( lab only, remove on production )
    requests.packages.urllib3.disable_warnings()  
  
  def get_content_views(self):
    '''
      Return Content View data
    '''
    url = '{}/katello/api/content_views?organization_id={}'.format(
      self.config['api_url'], 
      self.config['organization_id'])
    req = requests.get(
      f'{url}', 
      verify=False, 
      auth=(
        self.config['username'], 
        self.config['password']))
    if req.status_code == 200:
      data = json.loads(req.text)
      cv = []
      for r in data['results']:
        if len(r['repository_ids']) > 0:
          cv.append({
            'repositories' : r['repository_ids'],
            'id' : r['id'],
            'name' : r['name'],
            'last_published' : r['last_published'],
            'last_sync_repos' : self.get_repository_info(ids=r['repository_ids'])
          })
      return cv
    else:
      print(f'Error: {url} -> {req.reason}')
      sys.exit(1)

  def get_repository_info(self, **kwargs):
    '''
      This method is called by "get_content_views" method when it is
      runnig a loop to set the cv list.
      It's returns a timestamp that refers to last_sync repo.
    '''
    ids = kwargs['ids']
    sync_dates = []
    for id in ids:
      url = '{}/katello/api/repositories/{}?organization_id={}'.format(
        self.config['api_url'], 
        id ,
        self.config['organization_id'])
      req = requests.get(
        f'{url}', 
        verify=False, 
        auth=(
          self.config['username'], 
          self.config['password']))
      if req.status_code == 200:
        data = json.loads(req.text)
        if data['last_sync'] != None:
          if data['last_sync']['result'] == 'success' and data['last_sync']['state'] == 'stopped':
            ended_at = data['last_sync']['ended_at'].split()
            ea = f'{ended_at[0]} {ended_at[1]}'
            ea_dt = datetime.strptime(ea,'%Y-%m-%d %H:%M:%S')
            sync_dates.append(ea_dt)
      else:
        print(f'Error: {url} -> {req.reason}')
        sys.exit(1)
    return sync_dates  

  def publish_new_content_view(self, **kwargs):
    '''
      This method receives an content view id, and calls
      the Katello API to create a new version of this Content View.
    '''
    id = kwargs['id']
    url = '{}/katello/api/content_views/{}/publish'.format(
      self.config['api_url'],
      id
    )
    header = { 'Content-Type' : 'application/json' }
    req = requests.post(
      f'{url}', 
      verify=False, 
      auth=HTTPBasicAuth(
        self.config['username'],
        self.config['password']), 
        headers=header)
    if req.status_code == 200 or req.status_code == 202:
      return 'Success!'
    else:
      return f'error -> {url} {req.reason}'

  def run(self):
    '''
      Finally... this method will get all data ( content view and repositories ),
      compare dates between Content View and repositories and if necessary calls
      the method tha will create a new version of a Content View.
    '''
    cvs = self.get_content_views()
    log = open(self.log_file, 'a')
    log.write('\n--- Initializing Katello Content View Checker --- \n')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log.write(f'It\'s now       : {now} \n')
    for cv in cvs:
      name = cv['name']
      log.write(f'Content view   : {name} \n')
      last_published = cv['last_published'].split()
      lp = f'{last_published[0]} {last_published[1]}'
      lp_dt =  datetime.strptime(lp,'%Y-%m-%d %H:%M:%S')
      log.write(f'Last Published : {lp} \n')
      last_sync_repos = [ x > lp_dt for x in cv['last_sync_repos'] ]
      if True in last_sync_repos:
        log.write(f'Status         : It\'s necessary to publish a new version for this Content View \n')
        log.write(f'Action         : Creating a new version of a Content View... \n')        
        publish_content_view = self.publish_new_content_view(id=cv['id'])
        log.write(f'Action status  : {publish_content_view} \n')
      else:
        log.write(f'Status         : It\'s not necessary to publish a new version for this Content View \n')
    log.close()

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--env', required=True)
  args = vars(parser.parse_args())
  k = Katello(env=args['env'])
  k.run()