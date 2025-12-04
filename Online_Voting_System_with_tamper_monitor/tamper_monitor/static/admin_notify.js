(function(){
  function checkAlerts(){
    fetch('/tamper-monitor/alerts/count-unacked/', {credentials:'same-origin'})
      .then(resp => resp.json())
      .then(data => {
        if(data.count && data.count > 0){
          alert('Tamper Alert: ' + data.count + ' unacknowledged alert(s). Open Admin -> TamperAlerts.');
        }
      }).catch(()=>{});
  }
  setInterval(checkAlerts, 10000);
  checkAlerts();
})();
