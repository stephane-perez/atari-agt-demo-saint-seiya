import socket, subprocess, sys, time, os, re
# ringcheck_raw.py <warm>: realistic stack; dump the ring buffer and check every 4 KB piece against the signed music file
warm=float(sys.argv[1])
sock='/tmp/claude-0/hatari.sock'
if os.path.exists(sock): os.remove(sock)
srv=socket.socket(socket.AF_UNIX); srv.bind(sock); srv.listen(1)
cmd=['xvfb-run','-a','-s','-screen 0 800x600x24','hatari','--configfile','/home/claude/work/hatari.cfg','--machine','ste','--memsize','4096','--tos','/home/claude/work/tos162.img','--fast-boot','true','--sound','off','--frameskips','0','--statusbar','false','--borders','false','--harddrive','/home/claude/work/hd_acsi','--gemdos-drive','P','--acsi','0=/home/claude/work/acsi/disk.img','--disk-a','/home/claude/work/acsi/boot.st','--auto','P:\\SAINTS.PRG','--control-socket',sock,'--monitor','rgb','--fast-forward','true']
p=subprocess.Popen(cmd,stdout=open('/tmp/claude-0/rc.out','w'),stderr=subprocess.STDOUT)
srv.settimeout(20); conn,_=srv.accept()
def send(c): conn.sendall((c+'\n').encode())
time.sleep(warm)
send('hatari-debug memdump 0x3F0000 80'); time.sleep(2)
out=open('/tmp/claude-0/rc.out').read()
lines=re.findall(r'^\s*\$?0*(3[fF][0-9a-fA-F]{4}):\s*((?:[0-9a-fA-F]{2}\s*)+)',out,re.M)
hexs=''.join(''.join(d.split()) for a,d in lines)
b=bytes.fromhex(hexs); v=[int.from_bytes(b[i:i+4],'big') for i in range(0,80,4)]
ring,wr,size=v[6],v[7],v[10]
print('ring',hex(ring),'wr',wr,'ringsize(+40)',size,'raw state',hex(v[15]))
send('hatari-debug memdump 0x%X %d'%(ring,size)); time.sleep(40)
send('hatari-shortcut quit'); time.sleep(1); p.terminate()
out=open('/tmp/claude-0/rc.out').read()
d={}
for a,hx in re.findall(r'^([0-9A-Fa-f]{8}):\s*((?:[0-9a-fA-F]{2} ){1,16})',out,re.M):
    a=int(a,16)
    if ring<=a<ring+size: d[a]=bytes.fromhex(hx.replace(' ',''))
buf=b''.join(d[a] for a in sorted(d)); print('captured',len(buf),'of',size)
f=open('/tmp/short.sgn','rb').read() if not os.environ.get('LONG') else open('/home/claude/work/hd5_rel/MUSIC.SGN','rb').read()
data=f[44:44+4033092] if os.environ.get('LONG') else f[44:44+300000]
S=(44+len(data))//512; end=512*S-44
stream=data[:end]*((len(buf)//end)+3)
ok=bad=0; seams=[]
for o in range(0,len(buf)-4096+1,512):
    piece=buf[o:o+4096]; i=stream.find(piece[:64])
    if i>=0 and stream[i:i+4096]==piece: ok+=1
    else: bad+=1; seams.append(o)
print('512-step windows (4 KB) explained by the looped file:',ok,'not explained:',bad,seams[:12],'(wr at',wr,'-> expected about', 4096//512,'windows around it) loop length',end)
