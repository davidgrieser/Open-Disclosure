#!/usr/bin/python3

########################################################################
#
# File: GenerateTransactions.py
# Author: Matthew Leeds <mwl458@gmail.com>
# License: GNU GPL <http://www.gnu.org/licenses/gpl.html>
# Purpose: This script uses the four data files from alabamavotes.gov
# and the file produced by GenerateTransactees.py (for IDs)
# to collect every transaction formatted according to the data model.
# The output should have party_id, amount, filed_date, type,
# transaction_type, transaction_id, transactee_id, and
# amended for all records.
# -Expenditure data will also have explanation and purpose.
# -InKind data will also have inkind_nature and source_type.
# -Receipt data will also have endorsers and source_type.
# Everything is a string except endorsers, which is a list.
# Configuration parameters are read from 'config.ini'.
#
########################################################################

import json
import csv
from datetime import datetime
from configparser import ConfigParser
from uuid import uuid4

def main():
    # First read the config file.
    config = ConfigParser()
    config.read('config.ini')
    DATA_DIR = config.get('GENERATE_TRANSACTIONS', 'DATA_DIR')
    TRANSACTEES_FILE = config.get('GENERATE_TRANSACTEES', 'OUTFILE')
    DATAFILES = json.loads(config.get('GENERATE_TRANSACTIONS', 'DATAFILES'))
    OUTFILE = config.get('GENERATE_TRANSACTIONS', 'OUTFILE')
    PRETTY_PRINT = config.getboolean('GENERATE_TRANSACTIONS', 'PRETTY_PRINT')
    global allTransactees
    allTransactees = []
    try:
        with open(DATA_DIR + TRANSACTEES_FILE) as datafile:
            print('>> Loading ' + TRANSACTEES_FILE + '...', end='')
            allTransactees = json.load(datafile)
    except FileNotFoundError:
        print('>> ' + TRANSACTEES_FILE + ' not found! You should run GenerateTransactees.py.')
        exit(1)
    print(str(len(allTransactees)) + ' records loaded.')
    # hard code the values of record types for each file
    recordTypes = {}
    for filename in DATAFILES:
        if 'CashContribution' in filename:
            recordTypes[filename] = 'Contribution'
        elif 'InKindContribution' in filename:
            recordTypes[filename] = 'InKindContribution'
        elif 'Expenditure' in filename:
            recordTypes[filename] = 'Expenditure'
        elif 'OtherReceipts' in filename:
            recordTypes[filename] = 'Receipt'
        else:
            print('>> Unrecognized filename: ' + filename + '. Quitting.')
            sys.exit(1)
    # First load the output file from a previous run if it's there so we use the same id values.
    # TODO Should we look for a file for the previous year?
    oldTransactions = []
    try:
        with open(DATA_DIR + OUTFILE) as datafile:
           oldTransactions = json.load(datafile) 
    except FileNotFoundError:
        # This is a fresh run so new id's will be generated.
        pass
    # Make a dict out of oldTransactions so we have constant time access to id values
    global transactionIDs
    transactionIDs = {}
    for entry in oldTransactions:
        transactionIDs[entry['type'] + entry['transaction_id']] = entry['id']
    global allTransactions
    allTransactions = [] # master list of Transactions
    # Now load the transaction data from each file
    for filename in DATAFILES:
        with open(DATA_DIR + filename, errors='ignore', newline='') as datafile:
            print('>> Loading data from ' + filename)
            scrapeTransactions(csv.DictReader(datafile), recordTypes[filename])
    # output the data to a file
    print('>> Writing ' + str(len(allTransactions)) + ' records to ' + OUTFILE)
    with open(DATA_DIR + OUTFILE, 'w') as datafile:
        if PRETTY_PRINT:
            json.dump(allTransactions, datafile, sort_keys=True,
                      indent=4, separators=(',', ': '))
        else:
            json.dump(allTransactions, datafile)

def scrapeTransactions(records, recordType):
    global transactionIDs
    global allTransactions
    global allTransactees
    # idCol = ContributionID, ExpenditureID, InKindContributionID, or ReceiptID
    idCol = recordType + 'ID'
    # recordType = Contribution, Expenditure, or Receipt
    if recordType == 'InKindContribution':
        recordType = recordType[6:]
    # for each record, scrape the data and throw it in allTransactions
    for record in records:
        thisTransaction = {}
        thisTransaction['type'] = idCol[:-2] # cut off 'ID' part
        thisTransaction['transaction_type'] = record[recordType + 'Type'].strip()
        # find their record in allTransactees and get the ID
        foundMatch = False
        for entry in allTransactees:
            # if the txID's match, copy the UUID.
            if idCol[:-2] == entry['transaction_type'] and record[idCol] in entry['transaction_ids']:
                thisTransaction['transactee_id'] = entry['id']
                foundMatch = True
                break
        if not foundMatch:
            print('Error: No match found for id ' + record[idCol] + ' in the transactees file.')
        thisTransaction['transaction_id'] = record[idCol]
        # If the transaction exists in the dataset from a previous run, reuse the id.
        try:
            thisTransaction['id'] = transactionIDs[thisTransaction['type'] + thisTransaction['transaction_id']]
        except KeyError:
            thisTransaction['id'] = str(uuid4()).upper() # random unique id
        thisTransaction['party_id'] = record['OrgID']
        thisTransaction['amount'] = record[recordType + 'Amount']
        thisTransaction['filed_date'] = record['FiledDate']
        thisTransaction['amended'] = record['Amended']
        # add information specific to this record type
        if recordType == 'Expenditure':
            thisTransaction['explanation'] = record['Explanation'].lower()
            thisTransaction['purpose'] = record['Purpose'].lower()
        elif recordType == 'Receipt':
            endorsers = []
            colNames = ['EndorserName', 'EndorserAddress', 'EndorserGuaranteedAMT']
            for val in ['1','2','3']:
                endorser = [record[colNames[0] + val], record[colNames[1] + val], record[colNames[2] + val]]
                if sum(len(field) for field in endorser) > 0:
                    endorsers.append(endorser)
            if len(endorsers) > 0:
                thisTransaction['endorsers'] = endorsers
        elif idCol.startswith('InKindContribution'):
            thisTransaction['inkind_nature'] = record['NatureOfInKindContribution']
        allTransactions.append(thisTransaction)

if __name__=='__main__':
    main()
