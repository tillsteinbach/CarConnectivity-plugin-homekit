""" User interface for the HomeKit plugin in the Car Connectivity application. """
from __future__ import annotations
from asyncio import AbstractEventLoop
from typing import TYPE_CHECKING

import os
import asyncio
from io import BytesIO
from uuid import UUID
from pyqrcode import pyqrcode

import flask
from flask_wtf import FlaskForm
from wtforms import SubmitField
from flask_login import login_required

from carconnectivity_plugins.base.plugin import BasePlugin
from carconnectivity_plugins.base.ui.plugin_ui import BasePluginUI

from carconnectivity_plugins.homekit.plugin import Plugin

if TYPE_CHECKING:
    from typing import Optional, List, Dict, Union, Literal

    from carconnectivity.carconnectivity import CarConnectivity


class PluginUI(BasePluginUI):
    """
    A user interface class for the HomeKit plugin in the Car Connectivity application.
    """
    def __init__(self, plugin: BasePlugin):
        blueprint: Optional[flask.Blueprint] = flask.Blueprint(name='homekit', import_name='carconnectivity-plugin-homekit', url_prefix='/homekit',
                                                                    template_folder=os.path.dirname(__file__) + '/templates')
        super().__init__(plugin, blueprint=blueprint)

        class HomekitForm(FlaskForm):
            """
            HomekitForm class for handling the Homekit unpairing form.

            Attributes:
                unpair (SubmitField): A submit button labeled 'Unpair' for initiating the unpairing process.
            """
            unpair = SubmitField('Unpair')

        @self.blueprint.route('/', methods=['GET'])
        def root():
            return flask.redirect(flask.url_for('plugins.homekit.pairing'))

        @self.blueprint.route('/pairing', methods=['GET', 'POST'])
        @login_required
        def pairing():
            if isinstance(self.plugin, Plugin):
                plugin: Plugin = self.plugin

                form = HomekitForm()

                if form.unpair.data:
                    clients: list[UUID] = list(plugin._driver.state.paired_clients.keys()).copy()  # pylint: disable=protected-access
                    for client in clients:
                        try:
                            asyncio.get_event_loop()
                        except RuntimeError as ex:
                            if "There is no current event loop in thread" in str(ex):
                                loop: AbstractEventLoop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                        plugin._driver.unpair(client)  # pylint: disable=protected-access
                    plugin._driver.config_changed()  # pylint: disable=protected-access
                    flask.flash('Unpaired the Homekit bridge. You can now pair again')

                return flask.render_template('homekit/pairing.html', form=form, current_app=flask.current_app, homekit_plugin=plugin)
            return flask.abort(500, "HomeKit plugin not found")

        @self.blueprint.route('/accessories', methods=['GET'])
        @login_required
        def accessories():
            return flask.render_template('homekit/accessories.html', current_app=flask.current_app, homekit_plugin=self.plugin)

        @self.blueprint.route('/homekit-qr.png', methods=['GET'])
        @login_required
        def homekit_qr():
            if 'car_connectivity' not in flask.current_app.extensions:
                flask.abort(500, "Status picture doesn't exist.")
            car_connectivity: Optional[CarConnectivity] = flask.current_app.extensions['car_connectivity']
            if car_connectivity is not None:
                if 'homekit' in car_connectivity.plugins.plugins and car_connectivity.plugins.plugins['homekit'] is not None \
                        and isinstance(car_connectivity.plugins.plugins['homekit'], Plugin):
                    plugin: Plugin = car_connectivity.plugins.plugins['homekit']
                    if (accessory := plugin._driver.accessory) is not None:  # pylint: disable=protected-access
                        xhm_uri = accessory.xhm_uri()
                        qrcode = pyqrcode.create(xhm_uri)
                        img_io = BytesIO()
                        qrcode.png(img_io, scale=12)
                        img_io.seek(0)
                        return flask.send_file(img_io, mimetype='image/png')
            return flask.abort(500, "HomeKit plugin not found or wrong structure.")

    def get_nav_items(self) -> List[Dict[Literal['text', 'url', 'sublinks', 'divider'], Union[str, List]]]:
        """
        Generates a list of navigation items for the HomeKit plugin UI.
        """
        return super().get_nav_items() + [{"text": "Pairing", "url": flask.url_for('plugins.homekit.pairing')},
                                          {"text": "Accessories", "url": flask.url_for('plugins.homekit.accessories')},]

    def get_title(self) -> str:
        """
        Returns the title of the plugin.

        Returns:
            str: The title of the plugin, which is "HomeKit".
        """
        return "HomeKit"
