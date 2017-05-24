
function StreamResults(url) {
    var last_response_len = false;
    var has_progress = false;
    $.ajax({
        url: '/stream-results?url='+escape(url),
        dataType: "text",
        xhrFields:{
          onprogress: function(e) {
            var this_response, response = e.currentTarget.response;
            if (last_response_len === false) {
              this_response = response;
            } else {
              this_response = response.substring(last_response_len);
            }
            last_response_len = response.length;
            updateResultsTable(this_response);
            has_progress = true;
          }
        }
    })
    .done(function (data, status, xhr) {
      if (!has_progress) {
        updateResultsTable(data);
      }
      $('#loading').remove();
    });


}


function updateResultsTable(response) {
  var jsonRows;

  jsonRows = response.match(/[^\r\n]+/g);
  $(jsonRows).each(function(idx, obj) {
    notification = JSON.parse(obj);

    if (!notification.network_name) {
        return true;
    }

    trid = 'net_'+notification.network_name.replace(' ', '');

    if (notification.status == 'blocked') {
      destTable = '#active';
    } else if (notification.status == 'ok' && notification.last_blocked_timestamp != null) {
      destTable = '#past';
    } else {
      destTable = '#all';
    }

    console.log(trid + " " + destTable);
    isp_tr = $('#'+trid);

    console.log(isp_tr.length);

    if (isp_tr.length == 0) {
      console.log("Creating new tr");
      isp_tr = $("<tr>");
      isp_tr.attr('id', trid);
    };
    isp_tr.appendTo($(destTable));

    isp_tr.children().remove();
    if (destTable == '#active') {
        isp_tr.append(
          "<td>" + notification.network_name + "</td>"
          + "<td>" + notification.status_timestamp + "</td>"
          + "<td>" + notification.category + "</td>"
        );
    } else if (destTable == '#past') {
        isp_tr.append(
          "<td>" + notification.network_name + "</td>"
          + "<td>" + notification.status_timestamp + "</td>"
          + "<td>" + notification.last_blocked_timestamp + "</td>"
        );
    } else {
        isp_tr.append(
          "<td>" + notification.network_name + "</td>"
          + "<td>" + notification.status_timestamp + "</td>"
          + "<td></td>"
        );
    }


  });
}
