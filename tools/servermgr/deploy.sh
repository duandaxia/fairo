#!/bin/bash
# Copyright (c) Facebook, Inc. and its affiliates.



cd $(dirname $0)/../../
git push servermgr $(git subtree split --prefix tools/servermgr):master --force