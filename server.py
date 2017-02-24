
import argparse
import ConfigParser

import BlockedFrontend

parser = argparse.ArgumentParser()
parser.add_argument('-c', dest='config')
parser.add_argument('--dev', dest='dev', action='store_true')
args = parser.parse_args()

if args.config:
    cfg = ConfigParser.ConfigParser()
    cfg.read([args.config])
else:
    cfg = None

BlockedFrontend.run(cfg, dev=args.dev)
