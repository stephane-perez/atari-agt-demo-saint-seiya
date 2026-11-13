import socket,subprocess,sys,time,os,re
hd,prg=sys.argv[1],sys.argv[2]
tag=sys.argv[4] if len(sys.argv)>4 else 'x'
LOG='/tmp/claude-0/lt_%s.out'%tag
sock='/tmp/claude-0/lt_%s.sock'%tag
if os.path.exists(sock): os.remove(sock)
srv=socket.socket(socket.AF_UNIX); srv.bind(sock); srv.listen(1)
cmd=['xvfb-run','-a','-s','-screen 0 800x600x24','hatari','--configfile','/home/claude/work/hatari.cfg','--machine','ste','--memsize','4096','--tos','/home/claude/work/tos162.img','--fast-boot','true','--sound','off','--frameskips','0','--statusbar','false','--borders','false','--harddrive',hd,'--gemdos-drive','P','--auto',prg,'--control-socket',sock,'--monitor','rgb','--fast-forward','true']
p=subprocess.Popen(cmd,stdout=open('/tmp/claude-0/lt_%s.out'%tag+'','w'),stderr=subprocess.STDOUT)
srv.settimeout(30); conn,_=srv.accept()
def send(c): conn.sendall((c+'\n').encode())
t0=time.time()
res=None
time.sleep(2)
def dump(addr,n):
    n0=open(LOG).read().count('> memdump')
    send('hatari-debug memdump %s %d'%(addr,n))
    for _ in range(40):
        time.sleep(0.1)
        out=open(LOG).read()
        if out.count('> memdump')>n0 and re.search(r'\n[0-9A-Fa-f]{8}:.*\n?$',out): break
    L=re.findall(r'^\s*\$?0*([0-9a-fA-F]{1,8}):\s*((?:[0-9a-fA-F]{2}\s*)+)',out,re.M)
    return bytes.fromhex(''.join(L[-1][1].split()))
for i in range(int(sys.argv[3]) if len(sys.argv)>3 else 120):
    c=dump('0x3F0000',16); fr=int.from_bytes(c[8:12],'big')
    if fr>0:
        v=int.from_bytes(dump('0x466',16)[:4],'big'); res=(v-fr,time.time()-t0); break
send('hatari-shortcut quit'); time.sleep(1); p.terminate()
print('main loop started at _frclock=%d VBL (= %.1f s emulated at 50Hz), wall %.0f s'%(res[0],res[0]/50.0,res[1]) if res else 'not reached')
