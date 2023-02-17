# DEV

.changes file format description: <https://github.com/splitbrain/dokuwiki/blob/master/inc/ChangeLog/ChangeLogTrait.php>:

```
    'date'  => (int)$info[0], // unix timestamp
    'ip'    => $info[1], // IPv4 address (127.0.0.1)
    'type'  => $info[2], // log line type
    'id'    => $info[3], // page id
    'user'  => $info[4], // user name
    'sum'   => $info[5], // edit summary (or action reason)
    'extra' => $info[6], // extra data (varies by line type)
    'sizechange' => (isset($info[7]) && $info[7] !== '') ? (int)$info[7] : null, /
```

how to build .cahnges file: <https://github.com/splitbrain/dokuwiki/blob/master/inc/ChangeLog/ChangeLogTrait.php>:

```
# $strip = ['\t', '\n']

    'date'  => $timestamp ?? $info['date'],
    'ip'    => $info['ip'],
    'type'  => str_replace($strip, '', $info['type']),
    'id'    => $info['id'],
    'user'  => $info['user'],
    'sum'   => PhpString::substr(str_replace($strip, '', $info['sum']), 0, 255), # max 255 chars
    'extra' => str_replace($strip, '', $info['extra']),
    'sizechange' => $info['sizechange'], # $sizechange type: int(bytes) => = len($text) - len($currentContent)
```
