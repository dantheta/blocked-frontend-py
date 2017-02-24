
import argparse
import ConfigParser

import BlockedFrontend

parser = argparse.ArgumentParser()
parser.add_argument('-c', dest='config')
args = parser.parse_args()

if args.config:
    cfg = ConfigParser.ConfigParser()
    cfg.read([args.config])
else:
    cfg = None

BlockedFrontend.run(cfg)
