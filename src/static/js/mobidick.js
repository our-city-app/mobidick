var code_editor = null;
var call_result_request = null;
var call_result_response = null;
var current_api_method = null;
var call_result_dialog_content = null;
var call_result_dialog_spinner = null;
var call_result_dialog = null;
var create_new_link_dialog = null;
var visible_panels = [];

var splash_pgb = $("#splash_pgb").progressbar({
	value: 0
});

var splash_status = $("#splash_status");
var splash = $("#splash").dialog({
	title: 'Mobidick: Rogerthat sample service (loading ...)',
	width: 635,
	height: 542,
	modal: true,
	closeOnEscape: false,
	resizable: false,
	beforeClose: function(event, ui) { return true; }
});

var TYPE_CALL = 1;
var TYPE_CALLBACK = 2;

var function_click = function () {
	var sender = $(this);
	display_function(sender.parent().attr('api_category'), sender.text());
};

var mctracker = {
	day: 24*3600,
	months: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
	timezoneOffset: 60*new Date().getTimezoneOffset(),
	handleTimezone: function (timestamp) {
		return timestamp - mctracker.timezoneOffset;
	},
	nowUTC: function () {
		return Math.floor(new Date().getTime() / 1000);
	},
	now: function() {
		return mctracker.handleTimezone(mctracker.nowUTC());
	},
	formatDate: function (timestamp) {
		var now = mctracker.nowUTC();
		if (mctracker.isSameDay(now, timestamp)) {
			return mctracker.intToTime(mctracker.handleTimezone(timestamp)%mctracker.day, false);
		}
		var date = new Date(mctracker.handleTimezone(timestamp)*1000);
		if (mctracker.isSameYear(now, timestamp)) {
			return mctracker.months[date.getMonth()] + ' ' + date.getDate();
		}
		return date.toLocaleDateString();
	},
	isSameDay: function (timestamp1, timestamp2) {
		return Math.floor(timestamp1/mctracker.day) === Math.floor(timestamp2/mctracker.day);
	},
	isSameYear: function (timestamp1, timestamp2) {
		return new Date(timestamp1*1000).getFullYear() === new Date(timestamp2*1000).getFullYear();
	},
	intToTime: function (timestamp, includeSeconds) {
		var stub = function (number) {
			var string = ''+number;
			if (string.length == 1)
				return '0'+string;
			return string;
		};
		var hours = Math.floor(timestamp / 3600);
		var minutes = Math.floor((timestamp % 3600) / 60);
		if (includeSeconds) {
			var seconds = Math.floor((timestamp % 3600) % 60);
			return stub(hours) + ':' + stub(minutes) + ':' + stub(seconds);
		} else {
			return stub(hours) + ':' + stub(minutes);
		}
	},
	intToHumanTime: function (timestamp) {
		var hours = Math.floor(timestamp / 3600);
		var minutes = Math.floor((timestamp % 3600) / 60);
		var seconds = Math.floor((timestamp % 3600) % 60);
		if (hours > 0) {
			return hours + 'h ' + minutes + 'm ' + seconds + 's';
		} else if (minutes > 0) {
			return minutes + 'm ' + seconds + 's';
		} else {
			return seconds + 's';
		}
	},
};

var call_meta = {
	'friend.invite': {
		params: '{\n    "message": "Connect to our service to receive Belgian chocolate!", \n    "tag": "725985B4-B805-4F02-9971-FE61A60F9D27", \n    "email": "john.doe@foo.com", \n    "language": "nl", \n    "name": "John Doe"\n}',
		docs: 'http://www.rogerthat.net/developers/api-reference/#TPS_service_invites_Rogerthat_user',
		type: TYPE_CALL
	},
	'friend.break_up': {
		params: '{\n    "email": "john.doe@foo.com"\n}',
		docs: 'http://www.rogerthat.net/developers/api-reference/#TPS_breaks_friendship',
		type: TYPE_CALL
	},
	'friend.get_status': {
		params: '{\n    "email": "john.doe@foo.com"\n}',
		docs: 'http://www.rogerthat.net/developers/api-reference/#TPS_retrieves_status_of_a_user',
		type: TYPE_CALL
	},
	'friend.invited' : {
	    docs: 'http://www.rogerthat.net/developers/api-reference/#TPS_receives_friend_invitation',
	    type: TYPE_CALLBACK
	},
	'friend.invite_result' : {
		docs: 'http://www.rogerthat.net/developers/api-reference/#TPS_receives_user_friendship_status_update',
		type: TYPE_CALLBACK
	},
    'friend.broke_up': {
        docs: 'http://www.rogerthat.net/developers/api-reference/#TPS_receives_break_friendship_request',
        type: TYPE_CALLBACK
    },
    'friend.is_in_roles': {
        docs: 'http://www.rogerthat.net/developers/api-reference/', // TODO: anchor
        type: TYPE_CALLBACK
    },
	'messaging.send': {
		params: '{\n    "parent_key": null, \n    "branding": null, \n    "answers": [\n        {\n            "action": null, \n            "caption": "fine", \n            "ui_flags": 0, \n            "type": "button", \n            "id": "fine"\n        }, \n        {\n            "action": null, \n            "caption": "could do better", \n            "ui_flags": 0, \n            "type": "button", \n            "id": "notfine"\n        }\n    ], \n    "tag": "37AAF801-CE21-4AC5-9F43-E8E403E1EB5F", \n    "flags": 31, \n    "dismiss_button_ui_flags": 0, \n    "members": [\n        "john.doe@foo.com"\n    ], \n    "message": "Hey how are you",\n    "context": null\n}',
		docs: 'http://www.rogerthat.net/developers/api-reference/#TPS_sends_message_to_Rogerthat_user',
		type: TYPE_CALL
	},
	'messaging.update': {
		docs: 'http://www.rogerthat.net/developers/api-reference/#TPS_receives_message_update',
		type: TYPE_CALLBACK
	},
	'messaging.poke': {
		docs: 'http://www.rogerthat.net/developers/api-reference/#TPS_receives_user_poke',
		type: TYPE_CALLBACK
	},
	'messaging.form_update': {
		docs: 'http://www.rogerthat.net/developers/api-reference/#Form_answered_callback',
		type: TYPE_CALLBACK
	},
	'messaging.send_form': {
		params: '{\n    "parent_key": null,\n    "flags": 30,\n    "alert_flags": 2,\n    "branding": null,\n    "tag": "37AAF801-CE21-4AC5-9F43-E8E403E1EB5F",\n    "member":"john.doe@foo.com",\n    "message": "Please fill in a car brand",\n    "context":null,\n    "form": {\n        "positive_button": "Submit",\n        "negative_button": "Abort",\n        "positive_confirmation": null,\n        "negative_confirmation": "Are you sure you wish to abort?",\n        "positive_button_ui_flags": 0,\n        "negative_button_ui_flags": 0,\n        "type": "auto_complete",\n        "widget": {\n            "value": null,\n            "place_holder": "Car Brand",\n            "max_chars": 500,\n            "suggestions": [               \n                "Alpha Romeo",\n                "Aston Martin",\n                "BMW",\n                "Ferrari",\n                "Fiat",\n                "Ford",\n                "Maserati",\n                "Mazda",\n                "Mercedes",\n                "Mitsubishi",\n                "Saab",\n                "Seat",\n                "Skoda",\n                "Subaru",\n                "Suzuki",\n                "Volkswagen",\n                "Volvo"\n            ]\n        }\n    }\n}',
		docs: 'http://www.rogerthat.net/developers/api-reference/#Sending_a_form',
		type: TYPE_CALL
	},
	'messaging.seal': {
		params: '{\n    "parent_message_key": null, \n    "message_key": "b50d2ea1-3d43-47ab-8d1b-0ea94f5cfa77",\n    "dirty_behavior": 1\n}',
		docs: 'http://www.rogerthat.net/developers/api-reference/#Seal_Message',
		type: TYPE_CALL
	},
	'messaging.start_flow': {
		params: '{\n    "parent_message_key": null, \n    "flow": "ahNkZXZ-bW9iaWNhZ2VjbG91ZGhyck8LEgptYy10cmFja2VyIhVnLmF1ZGVuYWVydEBnbWFpbC5jb20MCxIRTWVzc2FnZUZsb3dEZXNpZ24iE1NhbXBsZSBtZXNzYWdlIGZsb3cM",\n    "members": ["john.doe@foo.com"],\n    "tag": null,\n    "context": null\n}',
		docs: 'http://www.rogerthat.net/developers/api-reference/#Launch_message_flow',
		type: TYPE_CALL
	},
    'messaging.start_chat': {
        params: '{\n    "alert_flags": 0, \n    "service_identity": null, \n    "topic": "Alarm situation in sector 5", \n    "tag": null, \n    "context": null, \n    "description": "Alarm situation", \n    "members": [\n        "john.doe@foo.com", \n        "jane.doe@foo.com"\n    ]\n}',
        docs: 'http://www.rogerthat.net/developers/api-reference/#Launch_message_flow',
        type: TYPE_CALL
    },
    'messaging.send_chat_message': {
        params: '{\n    "parent_key": "b2488800-938b-485c-b80b-c30f0126ee91",\n    "message": "The new chat message content.",\n    "answers": [],\n    "attachments": [],\n    "sender": {\n        "email": "john@example.com",\n        "name": "John Doe",\n        "language": "en",\n        "avatar_url": "https://rogerth.at/unauthenticated/mobi/cached/avatar/4824964683268096",\n        "app_id": "rogerthat"\n    },\n    "priority": 1,\n    "sticky": true,\n    "tag": null\n}',
        docs: 'http://www.rogerthat.net/developers/api-reference/#Launch_message_flow',
        type: TYPE_CALL
    },
    'messaging.delete_chat': {
        params: '{\n    "parent_message_key": "b2488800-938b-485c-b80b-c30f0126ee91"\n}',
        docs: 'http://www.rogerthat.net/developers/api-reference/#Launch_message_flow',
        type: TYPE_CALL
    },
	'messaging.flow_member_result': {
		docs: 'http://www.rogerthat.net/developers/api-reference/#Get_message_flow_result',
		type: TYPE_CALLBACK
	},
	'qr.create': {
		params: '{\n    "description": "description", \n    "tag": "tag",\n    "template_key": "template_key"\n}',
		docs: 'http://www.rogerthat.net/developers/api-reference/#Create_QR_Code_from_QR_Code_Template',
		type: TYPE_CALL
	},
	'system.list_message_flows': {
		params: '{}',
		docs: 'http://www.rogerthat.net/developers/api-reference/',
		type: TYPE_CALL
	}
};

var to_message_flow_run_row = function (mfr) {
	return $("<tr></tr>")
		.append($("<td></td>").text(mfr.description))
		.append($("<td></td>").text(mfr.member_count+""))
		.append($("<td></td>").attr("id", "mfr_member_result_count_"+mfr.key).text(mfr.member_result_count+""))
		.click(function () {
			window.open('/mfr/'+mfr.key,'_newtab');
		});
};

var to_message_flow_member_result_row = function (mfmr) {
	return $("<tr></tr>")
		.append($("<td></td>").text(mfmr.member))
		.append($("<td></td>").text(mfmr.description))
		.append($("<td></td>").text(mctracker.formatDate(mfmr.timestamp)))
		.append($("<td></td>").append($("<a></a>").attr("href", "/mfmr/"+mfmr.key+"?download=csv").text("download")));
};

var init_results_body_panel = function () {
	var tbody = $("#designer #panel #flow_results #results_body");
	var more_container = $("#designer #panel #flow_results #more_container");
	var more = $("#designer #panel #flow_results #more");
	var loading = $("#designer #panel #flow_results #loading");
	var cursor = null;
	$.ajax({
		url: '/get_flows',
		success: function (data) {
			cursor = data.cursor;
			$.each(data.list, function(i, mfr) {
				tbody.append(to_message_flow_run_row(mfr));
			});
			if (data.more)
				more_container.show()
			cursor = data.cursor;
			loading.hide();
		}
	});
	more.click(function () {
		loading.show();
		more_container.hide()
		$.ajax({
			url: '/get_flows?',
			data: {
				cursor: cursor
			},
			success: function (data) {
				cursor = data.cursor;
				$.each(data.list, function(i, mfr) {
					tbody.append(to_message_flow_run_row(mfr));
				});
				if (data.more)
					more_container.show()
				cursor = data.cursor;
				loading.hide();
			}
		});
	});
};

var init_flow_member_results_body_panel = function () {
	var tbody = $("#designer #panel #flow_member_results #results_body");
	var more_container = $("#designer #panel #flow_member_results #more_container");
	var more = $("#designer #panel #flow_member_results #more");
	var loading = $("#designer #panel #flow_member_results #loading");
	var cursor = null;
	$.ajax({
		url: '/get_flow_member_results',
		success: function (data) {
			cursor = data.cursor;
			$.each(data.list, function(i, mfr) {
				tbody.append(to_message_flow_member_result_row(mfr));
			});
			if (data.more)
				more_container.show()
			cursor = data.cursor;
			loading.hide();
		}
	});
	more.click(function () {
		loading.show();
		more_container.hide()
		$.ajax({
			url: '/get_flow_member_results?',
			data: {
				cursor: cursor
			},
			success: function (data) {
				cursor = data.cursor;
				$.each(data.list, function(i, mfr) {
					tbody.append(to_message_flow_member_result_row(mfr));
				});
				if (data.more)
					more_container.show()
				cursor = data.cursor;
				loading.hide();
			}
		});
	});
};

var to_poke_tag_message_flow_link_row = function (link) {
	var message_flow_name = null;
	$.each(message_flows, function (i, mf) {
		if (mf.identifier == link.message_flow)
			message_flow_name = mf.name;
	});
	var result_emails = link.result_emails;
	if (link.result_emails_to_identity_admins) {
	    if (result_emails)
	        result_emails += ', all admins of service identity';
	    else
	        result_emails = 'all admins of service identity';
	}
	return $("<tr></tr>").append($("<td></td>")
		.append($("<span></span>").addClass("data").addClass("break-up").text(link.description))
		.append($("<br>"))
		.append("tag: ")
		.append($("<span></span>").addClass("data").addClass("break-up").text(link.tag))
        .append($("<br>"))
        .append("Results mailed to: ")
		.append($("<span></span>").addClass("data").text(result_emails))
		.append($("<br>"))
		.prepend($("<a></a>").addClass("action-link").text("delete").click(function () {
			var done = send_call("Deleting mapping ...");
			$.ajax({
				url: '/delete_link',
				type: 'POST',
				data:{
					key: link.key
				},
				success: function () {
					done("Link deleted successfully!", 1000);
					refresh_links();
				}
			})
		})));
};

var refresh_links = function () {
	$.ajax({
		url: '/get_links',
		success: function (data) {
			var table_body = $("#designer #panel #poke_conf #pokes_body").empty();
			$.each(data, function (i, link){
				table_body.append(to_poke_tag_message_flow_link_row(link));
			});
		}
	});
};

var init_poke_conf_panel = function () {
	$("#add_poke_link").button().click(function () {
		create_new_link_dialog.dialog('open');
	});
	refresh_links();
};

var init_mass_invite_panel = function () {
	$("#designer #panel #mass_invite #submit").button().click(function () {
		var message_flow_name = null;
		var mf_id = $("#designer #panel #mass_invite #message_flow").val();
		$.each(message_flows, function (i, mf) {
			if (mf.identifier == mf_id)
				message_flow_name = mf.name;
		});
		var done = send_call("Sending invites ...");
		$.ajax({
			url: '/mass_invite',
			type: 'POST',
			data: {
				members: $("#designer #panel #mass_invite #email_addresses").val(),
				message_flow_id: mf_id,
				message_flow_name: message_flow_name,
                result_emails: $("#designer #panel #mass_invite #result_emails").val(),
				invite_message: $("#designer #panel #mass_invite #invite_message").val()
			},
			success: function () {
				done("Invites submitted successfully!", 1000);
			},
			error: function () {
				done("An unknown error occurred.");
			}
		});
	});
};

var display_function = function(category, func) {
	$("#developer #title").text(category + " API: " + func);
	$("#developer #documentation_url").attr('href', call_meta[func].docs);
	code_editor.setValue(call_meta[func].params);
	current_api_method = func;
};

var show_panel = function(obj, tabname) {
	var panel = obj.attr("panel");
	if (panel == visible_panels[tabname])
		return;
	var panel_container = $("#" + tabname + " #container #panel");
	var panel_count = panel_container.children().length;
	var i = 0;
	panel_container.children().fadeOut('slow', function () {
		i++;
		if (i == panel_count){
			if (! initiated_panels[panel]) {
				var init = init_panels[panel];
				if (init)
					init();
				initiated_panels[panel] = true;
			}
			$("#"+panel, panel_container).fadeIn('slow', function () {
				visible_panels[tabname] = panel;
			});
		}
	});
}

var show_designer_panel = function() {
	show_panel($(this), "designer");
};

var show_analysis_panel = function() {
	show_panel($(this), "analysis");
}

var load_screen_1 = function (done, next_index) {
	var i = 0;
	var panels = $(".mdpanel");
	panels.fadeIn('slow', function () {
		i++;
		if (i == panels.length)
			done(next_index);
	});
};

var load_screen_2 = function (done, next_index) {
	var editor_container = $("#developer #editor_container");
	var developer_menu = null;
	var designer_menu = null;
	var analysis_menu = null;
	var tabs = $("#tabs").tabs({
		show: function (event, ui) {
			if (ui.index == 0 && ! designer_menu) {
				designer_menu = $("#designer #menu").accordion({ header: "h3", fillSpace: true });
				$("#designer #panel #launch_flow #submit").button().click(submit_message_flow);
				$("li", designer_menu).click(show_designer_panel);
			} else if (ui.index == 1 && ! developer_menu) {
				developer_menu = $("#developer #menu").accordion({ header: "h3", fillSpace: true });
				$("li", developer_menu).click(function_click);
				code_editor = CodeMirror.fromTextArea($("#editor").get()[0], {
					mode:  {name: "javascript", json: true},
				    lineNumbers: true,
				    matchBrackets: true
				});
				$("#developer #submit").button().width(editor_container.width()).click(submit_api_call);
				display_function("Friends", "friend.invite");
			} else if (ui.index == 2 && ! analysis_menu) {
				analysis_menu = $("#analysis #menu").accordion({ header: "h3", fillSpace: true });
				$("li", analysis_menu).click(show_analysis_panel);
			}
		}
	});
	call_result_dialog_content = $("#call_result_dialog_content");
	call_result_dialog_spinner = $("#call_result_dialog_spinner");
	call_result_request = CodeMirror.fromTextArea($("#request_text", call_result_dialog_content).get()[0], {
		mode:  {name: "javascript", json: true},
	    lineNumbers: true,
	    matchBrackets: true,
	    readOnly: true
	});
	call_result_response = CodeMirror.fromTextArea($("#response_text", call_result_dialog_content).get()[0], {
		mode:  {name: "javascript", json: true},
	    lineNumbers: true,
	    matchBrackets: true,
	    readOnly: true
	});
	call_result_dialog = $("#call_result_dialog").dialog({
		autoOpen: false,
		width: 900,
		height: 750,
		modal: true,
		title: "Mobidick ===> Rogerthat cloud",
		resizable: false
	});
    $("#designer #panel #launch_flow #refresh_message_flow_list, #create_new_link_dialog #refresh_message_flow_list").click(function () {
        refresh_message_flow_list(function(){});
    });
    $("#create_new_link_dialog #refresh_branding_list").click(function () {
        refresh_branding_list(function(){});
    });
	create_new_link_dialog = $("#create_new_link_dialog").dialog({
		autoOpen: false,
		width: 500,
		height: 475,
		modal: true,
		title: "Map poke tag to message flow",
		resizable: false,
		buttons: {
			'Create mapping': create_message_flow_link,
			'Cancel': function () { create_new_link_dialog.dialog('close'); }
		}
	});
	done(next_index);
};

var load_screen_3 = function (done, next_index) {
	$("#options_save").button();
	done(next_index);
};

var create_message_flow_link = function () {
	var done = send_call("Creating mapping ...");
	var message_flow_name = null;
	var mf_id = $("#create_new_link_dialog #message_flow").val();
	$.each(message_flows, function (i, mf) {
		if (mf.identifier == mf_id)
			message_flow_name = mf.name;
	});
	$.ajax({
		url: '/create_link',
		data: {
			'tag': $("#create_new_link_dialog #tag").val(),
			'message_flow': mf_id,
			'message_flow_name': message_flow_name,
            'result_emails': $("#create_new_link_dialog #result_emails").val(),
            'result_emails_to_identity_admins': $("#create_new_link_dialog #result_emails_to_identity_admins").is(':checked'),
            'result_rogerthat_account': "",
            'result_branding': ""
		},
		type: 'POST',
		success: function (data) {
			if( data.success ) {
				done("Mapping created successfully!", 1000);
				create_new_link_dialog.dialog('close');
				refresh_links();
			} else {
				done(data.message);
			}
		},
		error: function () {
			done("Unkown error occurred while creating link.");
		}
	});
};

var connect_to_channel_api = function (done, next_index) {
	create_channel(function () {
		done(next_index);
	});
};

var submit_message_flow = function () {
	var done = send_call('Starting message flow ...');
	var message_flow_name = null;
	var mf_id = $("#designer #panel #launch_flow #message_flow").val();
	$.each(message_flows, function (i, mf) {
		if (mf.identifier == mf_id)
			message_flow_name = mf.name;
	});
	$.ajax({
		url: '/start_flow',
		type: 'POST',
		data: {
			members: $("#designer #panel #launch_flow #friend_accounts").val(),
			message_flow_id: mf_id,
			result_emails: $("#designer #panel #launch_flow #result_emails").val(),
			description: $("#designer #panel #launch_flow #description").val(),
			service_identity: $("#designer #panel #launch_flow #service_identity").val(),
			message_flow_name: message_flow_name
		},
		success: function (data) {
			if (data.valid_request && data.request_success) {
				done("Message flow started successfully!", 1500);
			}
			else {
				done("An error occurred trying to start the message flow:<br>"+data.error_message);
			} 
			if (data.valid_request) {
				add_call_to_logs("messaging.start_flow", data);
			}
			if (initiated_panels["flow_results"]) {
				var tbody = $("#designer #panel #flow_results #results_body");
				tbody.prepend(to_message_flow_run_row(data.mfr));
			}
		},
		error: function () {
			done("An unknown error occurred while starting the message flow!");
		}
	});
};

var send_call = function (title) {
	var call_done = false;
	var div = $("<div></div>");
	div.append($("<img></img>").attr("src", "/static/images/spinner40.gif"));
	div.dialog({
		title: title,
		modal: true,
		close: function () {
			return call_done;
		}
	});
	return function (message, timeout) {
		call_done = true;
		div.empty().html(message);
		if (timeout) {
			window.setTimeout(function () {div.dialog('close');}, timeout);
		}
	}
};

var load_message_flows = function (done, next_index) {
	refresh_message_flow_list(function () {
		done(next_index);
	});
};

var refresh_message_flow_list = function (onSuccess) {
    perform_call('system.list_message_flows', '{}', function (data) {
        var response = JSON.parse(data.response);
        if (! response.error) {
            var start_mf_mf_list = $("#create_new_link_dialog #message_flow, #launch_flow #message_flow, #mass_invite #message_flow");
            start_mf_mf_list.empty();
            message_flows = response.result;
            $.each(response.result, function(i, mfd) {
                start_mf_mf_list.each(function () {
                    $(this).append($("<option></option>").attr("value", mfd.identifier).text(mfd.name));
                });
            });
            $("#mass_invite #message_flow").prepend($("<option></option>"));
        }
        onSuccess();
    });
};

var load_brandings = function (done, next_index) {
    refresh_branding_list(function () {
        done(next_index);
    });
};

var refresh_branding_list = function (onSuccess) {
    perform_call('system.list_brandings', '{}', function (data) {
        var response = JSON.parse(data.response);
        if (! response.error) {
            var branding_list = $("#create_new_link_dialog #result_brandings");
            branding_list.empty();
            branding_list.prepend($("<option value=''>[no branding]</option>"));
            $.each(response.result, function(i, branding) {
                branding_list.each(function () {
                    $(this).append($("<option></option>").attr("value", branding.id).text(branding.description));
                });
            });
        }
        onSuccess();
    });
};

var loaders = 
	[	
	 	{status: 'Loading screen ...', func: load_screen_1},
	 	{status: 'Loading screen ...', func: load_screen_2},
	 	{status: 'Loading screen ...', func: load_screen_3},
	 	{status: 'Connecting to live update channel ...', func: connect_to_channel_api},
        {status: 'Loading list of message flows ...', func: load_message_flows},
        {status: 'Loading brandings ...', func: load_brandings}
    ];

var load = function (index) {
	splash_pgb.progressbar("value", index / loaders.length * 100);
	var loader = loaders[index];
	if (! loader) {
		splash.dialog('close');
		return;
	}
	splash_status.text(loader.status);
	loader.func(load, index+1);
};

var create_channel = function(onopen) {
	$.ajax({
		url: '/get_channel_token',
		type: 'POST',
		success: function (data) {
			var channel = new goog.appengine.Channel(data.token);
			var socket = channel.open();
			socket.onopen = onopen;
			socket.onclose = function () {
				var dialog = $("<div></div>").text("The live updating channel has been terminated. Close this window to create a new live updating channel.").dialog({
					title: 'Live updating channel terminated.',
					close: function () {
						create_channel(function () {
							dialog.dialog('close');
						});
						return false;
					}
				});
			};
			socket.onmessage = on_channel_message;
		},
		error: function () {
			alert('Could not setup live update channel.')
		},
	});
};

var on_channel_message = function (data) {
	data = JSON.parse(data.data);
	if (data.type == "callback") {
		add_call_to_logs(data.method, data);
	} else if (data.type == "mfr_update") {
		$("#mfr_member_result_count_"+data.mfr.key).text(data.mfr.member_result_count+"");
		$("#designer #panel #flow_member_results #results_body").prepend(to_message_flow_member_result_row(data.mfmr));
	}
};

var submit_api_call = function () {
	var show_dialog = $("#show_result").attr('checked');
	if (show_dialog)
		show_call_detail_dialog(current_api_method);
	perform_call(current_api_method, code_editor.getValue(), function (data) {
		if (show_dialog) {
			call_result_request.setValue(data.request);
			call_result_request.refresh();
			call_result_response.setValue(data.response);
			call_result_response.refresh();
			call_result_dialog_spinner.hide();
			call_result_dialog_content.fadeIn('slow');
		}
	}, function (error) {
		alert("Calling Rogerthat cloud failed.\nStatus: " + error.status + "\nResponse: \n" + error.responseText);
		call_result_dialog.dialog('close');
	});
};

var perform_call = function (method, parameters, onSuccess, onError) {
	$.ajax({
		url: '/call',
		type: 'POST',
		data: {
			'method': method,
			'params': parameters
		},
		success: function (data) {
			add_call_to_logs(method, data)
			onSuccess(data);
		},
		error: onError || function () {alert("Calling Rogerthat cloud failed.");}
	});
};

var add_call_to_logs = function (method, instance) {
	var timestamp = new Date();
	var meta = call_meta[method];
	var details = function () {
		show_call_detail_dialog(method, instance);
	};
	$("#bottom #calls thead tr th").show();
	$("#bottom #calls tbody").prepend($("<tr></tr>")
		.append($("<td></td>").text(meta && meta.type == TYPE_CALL ? 'Rogerthat API call' : 'Service API callback').click(details))
		.append($("<td></td>").text(method).click(details))
		.append($("<td></td>").text(timestamp.toTimeString()).click(details))
		.append($("<td></td>").text(JSON.parse(instance.response).error ? "Failure": "Success").click(details))
		.append(meta ? $("<td></td>").append($("<a></a>").text("documentation").attr("href", meta.docs).attr("target", "_blank")) : $("<td></td>")));
};

var show_call_detail_dialog = function(method, instance) {
	var meta = call_meta[method];
	call_result_dialog.dialog('option', 'title', (!meta || meta.type == TYPE_CALL) ? "Rogerthat API Call: "+method : "Service API Callback: "+method);
	if (instance) {
		call_result_request.setValue(instance.request);
		call_result_request.refresh();
		call_result_response.setValue(instance.response);
		call_result_response.refresh();
		call_result_dialog_spinner.hide();
		call_result_dialog_content.show();
	} else {
		call_result_dialog_spinner.show();
		call_result_dialog_content.hide();
	}
	call_result_dialog.dialog('open');		
};

var initiated_panels = {};
var init_panels = {
	flow_results: init_results_body_panel,
	flow_member_results: init_flow_member_results_body_panel,
	poke_conf: init_poke_conf_panel,
	mass_invite: init_mass_invite_panel
};

$("#document").ready(function () {
	load(0);
});
