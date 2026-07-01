frappe.ready(function () {
	// Badge numérique sur la cloche de notifications
	// Frappe v16 a le JS pour gérer .notifications-unseen mais n'injecte pas ces éléments dans le HTML.
	// Ce script ajoute un vrai badge counter sur le bouton cloche.

	var BADGE_ID = "dd-notif-badge";

	function getBadge() {
		return document.getElementById(BADGE_ID);
	}

	function getBell() {
		return document.querySelector(".sidebar-notification .item-anchor");
	}

	function injectBadge() {
		var bell = getBell();
		if (!bell || getBadge()) return;

		var badge = document.createElement("span");
		badge.id = BADGE_ID;
		badge.style.cssText = [
			"display:none",
			"position:absolute",
			"top:4px",
			"right:4px",
			"background:#e53935",
			"color:#fff",
			"border-radius:10px",
			"font-size:10px",
			"font-weight:700",
			"min-width:16px",
			"height:16px",
			"line-height:16px",
			"text-align:center",
			"padding:0 4px",
			"pointer-events:none",
			"z-index:9",
		].join(";");

		// Le bouton parent doit être en position relative
		var container = bell.closest(".sidebar-item-container");
		if (container) {
			container.style.position = "relative";
			container.appendChild(badge);
		}
	}

	function showBadge(count) {
		var badge = getBadge();
		if (!badge) return;
		if (count > 0) {
			badge.textContent = count > 99 ? "99+" : String(count);
			badge.style.display = "block";
		} else {
			badge.style.display = "none";
		}
	}

	function fetchCount() {
		frappe.call({
			method: "frappe.client.get_count",
			args: {
				doctype: "Notification Log",
				filters: {
					for_user: frappe.session.user,
					read: 0,
				},
			},
			callback: function (r) {
				showBadge(r.message || 0);
			},
		});
	}

	// Attente que la sidebar soit rendue
	var initInterval = setInterval(function () {
		if (getBell()) {
			clearInterval(initInterval);
			injectBadge();
			fetchCount();

			// Quand une nouvelle notification arrive → incrémenter ou refetch
			frappe.realtime.on("notification", function () {
				var badge = getBadge();
				if (!badge) return;
				var current = parseInt(badge.textContent, 10) || 0;
				showBadge(current + 1);
			});

			// Quand le panneau est ouvert → tout est marqué lu, badge à 0
			frappe.realtime.on("indicator_hide", function () {
				showBadge(0);
			});

			// Clic sur la cloche → refetch après délai (mark_all_as_read en cours)
			var bell = getBell();
			if (bell) {
				bell.addEventListener("click", function () {
					setTimeout(fetchCount, 800);
				});
			}
		}
	}, 300);
});
