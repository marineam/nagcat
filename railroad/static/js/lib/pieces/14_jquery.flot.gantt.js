/*
 * The MIT License

Copyright (c) 2010 by Juergen Marsch

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
*/
/*
Flot plugin for gantt data sets

  series: {
    gantt: { active: false,
             show: false,
             barHeight: 2
    }
  }
data: [

  $.plot($("#placeholder"), [{ data: [ ... ], gantt:{show: true} }])

*/

(function ($) {
    var options = {
        series: {
                        gantt: {active: false
                                , show: false
								, connectSteps: { show: false, lineWidth:2, color:"rgb(0,0,0)" }
                                , barHeight: .6
								, highlight: { opacity: 0.5 }
								, drawstep: drawStepDefault
                        }
                }
    };
    var  data = null, canvas = null, target = null, axes = null, offset = null, highlights = [];
 	function drawStepDefault(ctx,series,data,x,y,x2,color, isHighlight)
	{	if(isHighlight == false)
		{	ctx.beginPath();
			ctx.lineWidth = series.gantt.barheight;
			ctx.strokeStyle = "rgb(0,0,0)";
			ctx.moveTo(x, y);
			ctx.lineTo(x2, y);
			ctx.stroke();
		}
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = series.gantt.barheight - 2;
        ctx.lineCap = "butt";
		ctx.moveTo(x + 1, y);
        ctx.lineTo(x2 - 1, y);
        ctx.stroke();
	}
    function init(plot) 
	{	plot.hooks.processOptions.push(processOptions);
        function processOptions(plot,options)
        {   if (options.series.gantt.active)
            {   plot.hooks.draw.push(draw);
                plot.hooks.bindEvents.push(bindEvents);
                plot.hooks.drawOverlay.push(drawOverlay);
            }
        }
       	function draw(plot, ctx)
        {   var series;
            canvas = plot.getCanvas();
            target = $(canvas).parent();
            axes = plot.getAxes();           
            offset = plot.getPlotOffset();   
            data = plot.getData();
            for (var i = 0; i < data.length; i++)
            {	series = data[i];
			    series.gantt.barheight = axes.yaxis.p2c(1) / (axes.yaxis.max - axes.yaxis.min) * series.gantt.barHeight;
				if (series.gantt.show) 
				{	for (var j = 0; j < series.data.length; j++)
					{	drawData(ctx,series, series.data[j], series.color,false); }
					if(series.gantt.connectSteps.show)
					{	drawConnections(ctx,series); }
                }
            }
     	}
        function drawData(ctx,series,data,color,isHighlight)
        {	var x,y,x2;
            x = offset.left + axes.xaxis.p2c(data[0]);
            y = offset.top + axes.yaxis.p2c(data[1]);
            x2 = offset.left + axes.xaxis.p2c(data[2]);
			if (data.length == 4) 
			{	drawStepDefault(ctx, series, data, x, y, x2, color, isHighlight);}
			else
			{	series.gantt.drawstep(ctx,series,data,x,y,x2,color,isHighlight);}
        }
		function drawConnections(ctx,series)
		{	for(var i = 0; i < series.data.length; i++)
			{	for(var j = 0; j < series.data.length; j++)
				{	if(series.data[i][2] == series.data[j][0])
					{	var x = offset.left + axes.xaxis.p2c(series.data[i][2])
					       ,y = offset.top + axes.yaxis.p2c(series.data[i][1])
						   ,y2 = offset.top + axes.yaxis.p2c(series.data[j][1]);
						   drawConnection(ctx,x,y,y2,series.gantt.connectSteps.lineWidth,series.gantt.connectSteps.color);		   
					}
				}
			}
		}
		function drawConnection(ctx,x,y,y2,lineWidth,color)
		{	ctx.beginPath();
			ctx.lineWidth = lineWidth;
			ctx.strokeStyle = color;
			ctx.moveTo(x, y);
			ctx.lineTo(x, y2);
			ctx.stroke();
		}
        function bindEvents(plot, eventHolder)
        {   var r = null;
            var options = plot.getOptions();
            var hl = new HighLighting(plot, eventHolder, findNearby, options.series.gantt.active,highlights)
        }
        function findNearby(plot,mousex, mousey)
		{	var series, r;
            axes = plot.getAxes();
            for (var i = 0; i < data.length; i++) 
			{	series = data[i];
                if (series.gantt.show)
				{	for (var j = 0; j < series.data.length; j++) 
					{	var dataitem = series.data[j];
                        var dx = axes.xaxis.p2c(dataitem[0])
						  , dx2 = axes.xaxis.p2c(dataitem[2])
                          , dy = Math.abs(axes.yaxis.p2c(dataitem[1]) - mousey);
                        if (dy <= series.gantt.barheight / 2) 
						{	if (mousex >= dx && mousex <= dx2)
							{	r = { i: i, j: j }; }
						}
					}
            	}
        	}
         	return r;
    	}
        function drawOverlay(plot, octx)
        { 	octx.save();
            octx.clearRect(0, 0, target.width, target.height);
            for (i = 0; i < highlights.length; ++i) 
			{	drawHighlight(highlights[i]);}
            octx.restore();
            function drawHighlight(s)
			{	var c = "rgba(255, 255, 255, " + s.series.gantt.highlight.opacity + ")";
               	drawData(octx, s.series, s.point, c,true);
         	}
      	}
    }
    $.plot.plugins.push({
        init: init,
        options: options,
        name: 'gantt',
        version: '0.1'
    });
})(jQuery);
