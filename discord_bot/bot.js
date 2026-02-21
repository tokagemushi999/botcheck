
const { Client } = require('discord.js');
const client = new Client();

client.on('messageCreate', msg => {
    console.log(msg.content);
});

client.login('TOKEN');
