#!/usr/bin/python

'''
libvirtMonitor

monitoring kvm with libvirt and convert performance data into rrd. 

auther: Daniels Cai
date:  2013/05/14

'''

import libvirt
import sys
import os
import re
import time
import threading

class LibvirtMonitor():
    '''
    libvirt monitor class.

    data source driver supported : 
        LibvirtCollector
        CmdCollector

    data store drive supported:
        RRDStore
        CSVStore
        PNPStore
    '''
    def __init__(self,collector):
        self.collector=collector
        self.monitors=[]
        self.init_rrd_flag=0

    def add_monitor(self,monitor):
        self.monitors.append(monitor)

    def add_monitors(self,monitors):
        ''' add all monitors '''
        for monitor in monitors.monitors:
            self.add_monitor(monitor)


    def show_monitors(self):
        '''show all monitors classname'''
        for monitor in self.monitors:
            print monitor.__class__.__name__
        

    def run(self):
        '''
        run the data source get_res funtion
        each time res will write back to data store driver
        sleep 1 second for rest :)
        '''
        while True:
            self.res=self.collector.get_res()
            self.update()
            print "record add succefully"
            time.sleep(1)

    def update(self):
        #if self.init_rrd_flag==0:
        #    self.init_rrd()

        for monitor in self.monitors:
            monitor.update(self.res)

    def init_rrd(self):
        for monitor in self.monitors:
            monitor.init_rrd(self.res)


class BaseLibvirt2rrd():
    '''
    main libvirt 2 rrd class
    need to initialize a driver to spawn a new instance
    monitors should be specified with MakeMonitor class

    '''

    def __init__(self,remote=None):
        self.observers=[]
        self.init_rrd_flag=0

    def addMonitor(self,observer):
        self.observers.append(observer)

    def addMonitors(self,monitors):
        for monitor in monitors:
            self.addMonitor(monitor)

    def showMonitors(self):
        for observer in  self.observers:
            print observer.__class__.__name__

    def run(self):
        while True:
            self._run()
            time.sleep(1)

    def update(self):
        if self.init_rrd_flag==0:
            self.init_rrd()
        mythreads = []
        for observer in self.observers:
            thread_name=threading.Thread(
                    target=observer.update,args=(self.res,))
            mythreads.append(thread_name)
        for i in mythreads:
            i.start()

        for i in mythreads:
            i.join()

    def init_rrd(self):
        for observer in self.observers:
            observer.init_rrd(self.res)

class Collector():
    '''
    vm infomation Collector abstract driver class 
    get_res return a dict to Libvirt2rrd instance 
    '''

    def get_res(self):
        pass


class LibvirtCollector(BaseLibvirt2rrd):
    '''
    use python-libvirt to retrieve infomation, 
    not implemented yet
    '''

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

class CmdCollector(Collector,object):
    '''
    use command line to retrieve infomation 
    command like: 
        /usr/bin/virt-top -n 2 -d 1 --block-in-bytes --stream

    notice that -d params is specified , 
    we need to discard the first data

    '''

    def get_res(self):
        self._get_res()
        return self.res

    def _get_res(self):
        cmd='/usr/bin/virt-top -n 2 -d 1 --block-in-bytes --stream'
        data=os.popen(cmd).read()
        self.convert_to_dict(data)

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


class BaseMonitor():
    '''
    rrd observer template class 
    get a dict from Libvirt2rrd ,
    convert it into rrd ,or other datastore

    right now, only rrd is supported ,
    more store driver will be added in the futrue .
    '''


    def __init__(self):
        self.path='/tmp/dcai/rrd'

    def _safe_make_dir(self,path_uuid):
       if not os.path.exists(path_uuid):
           os.makedirs(path_uuid)

    def _safe_create_rrd(self,uuid,rrdname):
        path_uuid=self.path+'/'+uuid
        if not os.path.exists(path_uuid+'/'+self.rrdname):
            cmd="/usr/bin/rrdtool create %s/%s -s 1 DS:CPU:GAUGE:10:U:U RRA:AVERAGE:0.5:10:3153600" % (path_uuid,rrdname)
            os.popen(cmd)

    def _update_rrd(self,uuid,rrdname,time,usage):
        path_uuid=self.path+'/'+uuid
        cmd="/usr/bin/rrdtool update %s/%s %s:%s" % \
                (path_uuid,rrdname,time,usage)
        os.popen(cmd).read()

    def update(self,res):
        print "reporter: %s  " % self.name

    def init_rrd(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)

class CPUMonitor(BaseMonitor,object):
    '''
    observe cpu info
    '''
    def __init__(self):
        super(CPUMonitor, self).__init__()

        self.name='cpu monitor'
        self.rrdname='cpu.rrd'

    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['CPU'])



class MemoryMonitor(BaseMonitor,object):
    '''
    observer memory info
    memory infomation is not the real memory cosumption in vm ,
    virt-fish should be a good solution for this 

    right now, this is not usable 
    '''

    def __init__(self):
        super(MemoryMonitor,self).__init__()
        self.name='memory monitor'
        self.rrdname='mem.rrd'

    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['MEM'])



class DiskReadbondMonitor(BaseMonitor,object):
    ''' 
    observer disk read info
    '''
    def __init__(self):
        super(DiskReadbondMonitor,self).__init__()
        self.name='disk inbound monitor'
        self.rrdname='disk_read.rrd'

    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['RDBY'])


class DiskWriteMonitor(BaseMonitor,object):
    ''' 
    observer disk write info
    '''
    def __init__(self):
        super(DiskWriteMonitor,self).__init__()
        self.name='disk outbound monitor'
        self.rrdname='disk_write.rrd'
    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['WRBY'])


class NetworkInboundMonitor(BaseMonitor,object):
    ''' 
    observer network inbound info
    '''
    def __init__(self):
        super(NetworkInboundMonitor,self).__init__()
        self.name='network inbound monitor'
        self.rrdname='network_in.rrd'
    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['CPU'])


class NetworkOutboundMonitor(BaseMonitor,object):
    ''' 
    observer network outbound info
    '''
    def __init__(self):
        super(NetworkOutboundMonitor,self).__init__()
        self.name='network outbound monitor'
        self.rrdname='network_out.rrd'
    def update(self,res):
        for uuid in res.keys():
            path_uuid=self.path+'/'+uuid
            self._safe_make_dir(path_uuid)
            self._safe_create_rrd(uuid,self.rrdname)
            self._update_rrd(uuid,self.rrdname,res[uuid]['TIME'],res[uuid]['CPU'])



class Store():
    '''
    back end store abstract class
    '''
    pass

class RRDStore(Store):
    '''
    rrd store class
    not implement yet
    '''
    pass

class CSVStore(Store):
    '''
    csv store class
    not implement yet
    '''
    pass

class PNPStore(Store):
    '''
    pnp driver class 
    save data into pnp  spool
    '''


class MakeMonitors():
    def __init__(self,store,resource):
        self.monitors=[]
        self.store=store
        self.resource=resource
        self.add_monitors()

    def add_monitors(self):
        if 'cpu' in self.resource:
            cpu=CPUMonitor()
            self.monitors.append(cpu)

        if 'mem' in self.resource:
            mem=MemoryMonitor()
            self.monitors.append(mem)

        if 'disk_read' in self.resource:
            disk_read=DiskReadbondMonitor()
            self.monitors.append(disk_read)

        if 'disk_write' in self.resource:
            disk_write=DiskWriteMonitor()
            self.monitors.append(disk_write)

        if 'net_in' in self.resource:
            net_in=NetworkInboundMonitor()
            self.monitors.append(net_in)

        if 'net_out' in self.resource:
            net_out=NetworkOutboundMonitor()
            self.monitors.append(net_out)
    

if __name__ == '__main__':
    collector=CmdCollector()
    lmon=LibvirtMonitor(collector)

    store=PNPStore()
    resource=['cpu','disk_read','disk_write','net_in','net_out']
    monitors=MakeMonitors(store,resource)

    lmon.add_monitors(monitors)
    lmon.show_monitors()
    lmon.run()
    
