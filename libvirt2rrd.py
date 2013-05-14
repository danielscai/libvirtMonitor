#!/usr/bin/python

'''
libvirt2rrd

monitoring kvm with libvirt and convert performance data into rrd. 

auther: Daniels Cai
date:  2013/05/14

'''

import libvirt
import sys

conn = libvirt.openReadOnly(None)
if conn == None:
    print 'Failed to open connection to the hypervisor'
    sys.exit(1)

domains=conn.listAllDomains(1)

for dom0 in domains:
    print "Domain : id %d running %s" % (dom0.ID(), dom0.OSType())
    print dom0.info()
    

