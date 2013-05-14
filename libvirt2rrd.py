#!/usr/bin/python

'''
libvirt2rrd

monitoring kvm with libvirt and convert performance data into rrd. 

auther: Daniels Cai
date:  2013/05/14

'''

import libvirt
import sys
import os
import re
import time



class BaseLibvirt2rrd():
    def __init__(self,remote=None):
        self.observers=[]

    def addObserver(self,observer):
        self.observers.append(observer)

    def addMonitors(self,monitors):
        for monitor in monitors:
            self.addObserver(monitor)

    def showMonitors(self):
        for observer in  self.observers:
            print observer.__class__.__name__

    def update(self):
        for observer in self.observers:
            observer.update(self.res)

class RRDChecker(BaseLibvirt2rrd):
    def __init__(self,remote=None):
        self.conn = libvirt.openReadOnly(remote)
        self.observers=[]
        if self.conn == None:
            print 'Failed to open connection to the hypervisor'
            sys.exit(1)
        self.getDomains()

    def getDomains(self):
        self.domains=self.conn.listAllDomains(1)

    def loopDomains(self):
        for dom0 in self.domains:
            print "Domain : id %d running %s,uuid  %s" % \
                    (dom0.ID(), dom0.OSType(),dom0.UUIDString())

    def run(self):
        while True:
            for dom in self.domains:
                self.update(dom,self.conn)
            time.sleep(1)

    def update(self):
        for observer in self.observers:
            observer.update(self.res)

class CmdChecker(BaseLibvirt2rrd):

    def run(self):
        while True:
            self._run()
            time.sleep(1)
            print "recorded successfully"

    def _run(self):
        cmd='/usr/bin/virt-top -n 2 -d 1 --block-in-bytes --stream'
        data=os.popen(cmd).read()
        self.convert_to_dict(data)
        self.update()

    def convert_to_dict(self,data):
        tmp=re.match(u'.*TIME\s*NAME(.*)',data,re.S)
        reses=tmp.groups(0)[0]
        res_tmp=reses.split('\n')
        res=res_tmp[1:-1]
        all_res={}
        for _res in res:
            tmp=re.split(u'\s*',_res)
            now=int(time.time())
            tmp_dict={
                    'ID':tmp[1],
                    'S':tmp[2],
                    'RDBY':tmp[3].strip('K'),
                    'WRBY':tmp[4].strip('K'),
                    'RXBY':tmp[5],
                    'TXBY':tmp[6],
                    'CPU':tmp[7],
                    'MEM':tmp[8],
                    'TIME':tmp[9],
                    'NAME':tmp[10],
                    'TIME':now,}
            uuid=self._get_uuid(tmp_dict['NAME'])
            
            all_res[uuid]=tmp_dict
        self.res=all_res

    def _get_uuid(self,name):
        cmd="/usr/bin/virsh dumpxml %s | grep '<uuid>'" % name
        data=os.popen(cmd).read()
        r=re.match(u'.+>(.*)<',data,re.S)
        uuid=r.groups(0)[0]
        #return uuid

        #cmd="/usr/bin/virsh domuuid %s" % name 
        #uuid=os.popen(cmd).read()
        #uuid.strip()
        return uuid

    def _get_cpu_percent(self,):
        pass


class BaseObserver():
    def __init__(self):
        self.path='/tmp/dcai/rrd'

    def _safe_make_dir(self,path_uuid):
       if not os.path.exists(path_uuid):
           os.makedirs(path_uuid)

    def _safe_create_rrd(self,uuid,rrdname):
        path_uuid=self.path+'/'+uuid
        if not os.path.exists(path_uuid+'/'+self.rrdname):
            cmd="/usr/bin/rrdtool create %s/%s -s 1 DS:CPU:GAUGE:10:U:U RRA:LAST:0.5:5:6307200" % (path_uuid,rrdname)
            os.popen(cmd)

    def _update_rrd(self,uuid,rrdname,time,usage):
        path_uuid=self.path+'/'+uuid
        cmd="/usr/bin/rrdtool update %s/%s %s:%s" % \
                (path_uuid,rrdname,time,usage)
        os.popen(cmd).read()

    def update(self):
        print "reporter: %s  " % self.name

class CPUObserver(BaseObserver,object):
    def __init__(self):
        super(CPUObserver, self).__init__()

        self.name='cpu monitor'
        self.rrdname='cpu.rrd'

    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['CPU'])



class MemoryObserver(BaseObserver,object):
    def __init__(self):
        super(MemoryObserver,self).__init__()
        self.name='memory monitor'
        self.rrdname='mem.rrd'

    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['MEM'])



class DiskInbondObserver(BaseObserver,object):
    def __init__(self):
        super(DiskInbondObserver,self).__init__()
        self.name='disk inbound monitor'
        self.rrdname='disk_read.rrd'

    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['RDBY'])


class DiskOutbondObserver(BaseObserver,object):
    def __init__(self):
        super(DiskOutbondObserver,self).__init__()
        self.name='disk outbound monitor'
        self.rrdname='disk_write.rrd'
    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['WRBY'])


class NetworkInboundObserver(BaseObserver,object):
    def __init__(self):
        super(NetworkInboundObserver,self).__init__()
        self.name='network inbound monitor'
        self.rrdname='network_in.rrd'
    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['CPU'])


class NetworkOutboundObserver(BaseObserver,object):
    def __init__(self):
        super(NetworkOutboundObserver,self).__init__()
        self.name='network outbound monitor'
        self.rrdname='network_out.rrd'
    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['CPU'])



class Driver():
    pass

class RRDDriver(Driver):
    pass

class CSVDriver(Driver):
    pass


class CheckDriver():
    pass

class CMDChecker(CheckDriver):
    pass

class MakeMonitors():
    def __init__(self,*args,**kwgs):
        self.monitors=[]
        self.make_monitor(*args,**kwgs)

    def make_monitor(self,*args,**kwgs):
        if 'cpu' in args:
            cpu=CPUObserver()
            self.monitors.append(cpu)

        if 'mem' in args:
            mem=MemoryObserver()
            self.monitors.append(mem)

        if 'disk_in' in args:
            disk_in=DiskInbondObserver()
            self.monitors.append(disk_in)

        if 'disk_out' in args:
            disk_out=DiskOutbondObserver()
            self.monitors.append(disk_out)

        if 'net_in' in args:
            net_in=NetworkInboundObserver()
            self.monitors.append(net_in)

        if 'net_out' in args:
            net_out=NetworkOutboundObserver()
            self.monitors.append(net_out)
    

if __name__ == '__main__':
    #l2rrd=Libvirt2rrd()
    #l2rrd=RRDChecker()
    #print dir(l2rrd)
    l2rrd=CmdChecker()
    #l2rrd.loopDomains()
    #monitor=MakeMonitors('cpu','mem','disk_in','disk_out','net_in','net_out')
    monitor=MakeMonitors('cpu','disk_in','disk_out','net_in','net_out')
    l2rrd.addMonitors(monitor.monitors)
    #l2rrd.showMonitors()
    l2rrd.run()
    
