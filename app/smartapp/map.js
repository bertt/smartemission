$(document).ready(function () {

			//$('table1').hide();   
			//$("button").click(function(){
			//$("table1").toggle();
			//});

    // create the tile layer with correct attribution
    var map = new L.Map('map', {zoom: 13, center: new L.latLng([51.8348, 5.85])});
    var osmUrl = 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    var osmAttrib = 'Map data <a href="http://openstreetmap.org">OpenStreetMap</a> contributors';
    var osmTiles = new L.TileLayer(osmUrl, {attribution: osmAttrib});
    map.addLayer(osmTiles);
    var source = $("#entry-template").html();
    var template = Handlebars.compile(source);

    // See http://stackoverflow.com/questions/11916780/changing-getjson-to-jsonp
    // Notice the callback=? . This triggers a JSONP call


    var locaties = 'http://api.smartemission.nl/sosemu/api/v1/stations?format=json&callback=?';
    $.getJSON(locaties, function (data) {
        var geojson = L.geoJson(data, {
				pointToLayer: function(feature, latlng) {
					var locatie = new L.icon({
						iconUrl: 'locatie-icon.png',
						iconSize: [24, 41],
						iconAnchor: [10, 40]
					});
					return L.marker(latlng, {icon: locatie});
				}
		}).addTo(map)

            .on('click', function (e) {
                var stationId = e.layer.feature.properties.id;
                var timeseriesUrl = 'http://api.smartemission.nl/sosemu/api/v1/timeseries?station=' + stationId + '&callback=?';

				$.getJSON(timeseriesUrl, function (data) {
					
					// Split into categories for ease of templating: gasses, meteo and audio
                    var gasLabels = 'CO2,CO,NO2,O3,NH3';
                    var meteoLabels = 'Temperatuur,Luchtdruk,Luchtvochtigheid';
                    var audioLabels = 'Audio Maxvalue,Audio/Noise Level 1-5';

                    // See to which category an observation belongs by matching the label
                    var gasses = [];
                    var meteo = [];
                    var audio = [];

                    for (var idx in data) {
                        var component = data[idx];
                        var label = component.parameters.phenomenon.label;

                        // Is it a gas?
                        if (gasLabels.indexOf(label) >= 0) {
                            gasses.push(component);

                        // Is it a meteo?
                        } else if (meteoLabels.indexOf(label) >= 0) {
                            meteo.push(component);

                        // Is it audio?
                        } else if (audioLabels.indexOf(label) >= 0) {
                            // Is it a audio?
                            audio.push(component);
                        }

                    }

                    // Create station data struct: splitting up component categories
                    var stationData = {
                        station: e.layer.feature,
                        data: {
                            gasses: gasses,
                            meteo: meteo,
                            audio: audio
                        }

                    };
                    console.log(stationData);

                    var html = template(stationData);

                    // Hier met JQuery
                    var sidebarElm = $("#sidebar");

                    // sidebarElm clear first
                    sidebarElm.empty();
                    sidebarElm.append(html);
                    sidebar.toggle();

                    //Coordinaten verkeerd om, zoom in zee bij Somalie. (5.85 , 51,83)
						//var zoom = 	e.layer.feature.geometry.coordinates;
						//map.setView(zoom, 18);
					
                });


            });
    });


    var sidebar = L.control.sidebar('sidebar', {
        closeButton: true,
        position: 'left'
    });
    map.addControl(sidebar);

    var locatie = L.icon({
        iconUrl: 'locatie-icon.png',
        iconSize: [24, 41],
        iconAnchor: [10, 40]
    });

    var locatieclick = L.icon({
        iconUrl: 'locatie-icon-click.png',
        iconSize: [24, 41],
        iconAnchor: [10, 40]
    });


    map.on('click', function () {
        sidebar.hide();
        map.setView([51.8348, 5.85], 13);
    });
    sidebar.on('show', function () {
        console.log('Sidebar will be visible.');
    });
    sidebar.on('shown', function () {
        console.log('Sidebar is visible.');
    });
    sidebar.on('hide', function () {
        console.log('Sidebar will be hidden.');
    });
    sidebar.on('hidden', function () {
        console.log('Sidebar is hidden.');
    });

    sidebar.on(sidebar.getCloseButton(), 'click', function () {
        console.log('Close button clicked.');
    });

});
