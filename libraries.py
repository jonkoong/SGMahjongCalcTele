"""
The imports the bot actually uses, in the one place the 2022 file kept them.

Only names used by a project file belong here. `util.py` was the reason this shim existed and is
gone; `mjbot.py` star-imports it, so an entry that nothing reads is a dead dependency wearing an
import — which is how `beautifulsoup4` survived two rewrites.
"""
import config
import telebot
from telebot import types
import requests
from flask import Flask, request
