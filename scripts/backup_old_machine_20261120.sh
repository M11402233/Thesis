#!/bin/bash
# Back up old-machine diagnostic data to the new machine and verify (size + sha256). Read-only on the old machine. Nothing is deleted.
set -u
SRC=$HOME/oran-zt-kpm-verification/data
DSTH=cindy@127.0.0.1; PORT=2222
DST=oran-zt-kpm-verification/data/old_machine_backup_20261120
LOG=$HOME/backup_old_machine_20261120.log
exec > "$LOG" 2>&1
echo "start $(date '+%F %T')"
ssh -p $PORT $DSTH "test -e $DST && echo EXISTS" | grep -q EXISTS && { echo "DST exists, abort"; exit 1; }
ssh -p $PORT $DSTH "mkdir -p $DST"
for d in r5_runs r7_validate d30h_memdiag; do
  echo "== rsync $d $(date '+%T')"
  rsync -a -e "ssh -p $PORT" "$SRC/$d" "$DSTH:$DST/" || { echo "rsync $d FAILED"; exit 1; }
done
echo "== manifests $(date '+%T')"
( cd "$SRC" && find r5_runs r7_validate d30h_memdiag -type f -print0 | sort -z | xargs -0 sha256sum ) > $HOME/backup_old_machine_20261120.local.sha256
ssh -p $PORT $DSTH "cd $DST && sha256sum -c --quiet -" < $HOME/backup_old_machine_20261120.local.sha256 > $HOME/backup_old_machine_20261120.verify.txt 2>&1
rc=$?
nloc=$(wc -l < $HOME/backup_old_machine_20261120.local.sha256)
nrem=$(ssh -p $PORT $DSTH "cd $DST && find r5_runs r7_validate d30h_memdiag -type f | wc -l")
echo "files local=$nloc remote=$nrem sha256sum -c rc=$rc"
echo "bytes local=$(cd $SRC && du -sb r5_runs r7_validate d30h_memdiag | awk '{s+=$1}END{print s}') remote=$(ssh -p $PORT $DSTH "cd $DST && du -sb r5_runs r7_validate d30h_memdiag | awk '{s+=\$1}END{print s}'")"
[ $rc -eq 0 ] && [ "$nloc" = "$nrem" ] && echo VERIFIED || echo MISMATCH
echo "end $(date '+%F %T')"
