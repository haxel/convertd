convertd
========

A small daemon to convert videos to 3gp or flv - used in spaceplace website

$socket = socket_create(AF_UNIX, SOCK_STREAM, 0);
if(socket_connect($socket,"path/to/convertd.sock") !== false) 
{
    $message = $filename . " | 3gp\n";
    socket_send( $socket,$message,strlen($message),0x100);
}
socket_close($socket);      
