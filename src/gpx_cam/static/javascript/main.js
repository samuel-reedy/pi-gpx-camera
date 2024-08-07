class Center {
    constructor() {
        this.stream = document.getElementById("stream");
        this.canvas = document.getElementById("canvas");
        this.context = this.canvas.getContext('2d');
        this.fps = 0;
        this.frameTimes = [];
        this.maxFrameCount = 10;
    }

    render() {
    }
}

window.onload = function() {
    var ws
    const jmuxer = new JMuxer({
        node: 'stream',
        mode: 'video',
        flushingTime: 0,
        fps: 20,
        debug: false
    });

    const center = new Center();

    function startWebSocket() {
        const ip = document.getElementById('ip').value;
        const port = document.getElementById('port').value;
        ws = new WebSocket([`ws://${ip}:${port}/ws/`]);
        ws.binaryType = 'arraybuffer';

        ws.addEventListener('message', function(event) {
            if (!document.hidden) {
                jmuxer.feed({
                    video: new Uint8Array(event.data)
                });

                center.render();
            }
        });

        ws.addEventListener('close', function() {
            console.log('WebSocket closed, retrying...');
            setTimeout(startWebSocket, 1000);
        });
    }

    startWebSocket();

    window.onresize = function() {
        center.render();
    };
    window.one = function() {
        center.render();
    };
};

function openFileManager() {
    window.open("http://192.168.2.3:8085", "_blank");
}

function openParameters() {
    window.open("http://192.168.2.3:8075/parameters", "_blank");
}


