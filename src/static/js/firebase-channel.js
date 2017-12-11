function FirebaseChannel(config, customToken, basePath, uid, onConnected, onMessage, onError) {
    this.customToken = customToken;
    this.basePath = basePath;
    this.uid = uid;
    this.onConnected = onConnected;
    this.onMessage = onMessage;
    this.onError = onError;

    firebase.initializeApp(config);
    this.initTime = parseInt(new Date().getTime() / 1000);
}


FirebaseChannel.prototype = {
    connect: function() {
        firebase.auth().signInWithCustomToken(this.customToken).then(this.connected.bind(this)).catch(this.onError.bind(this));
    },

    connected: function() {
        this.onConnected();
        this.setupHandlers();
    },

    valueChanged: function(data) {
        var value = data.val();
        if(value && value.timestamp >= this.initTime) {
        		console.log("--------- channel ---------\n", value.data);
            this.onMessage(JSON.parse(value.data));
        }
    },

    setupHandlers: function() {
        var nodeRef = firebase.database().ref(this.basePath).child(this.uid);
        nodeRef.on('value', this.valueChanged.bind(this));
    },
};
